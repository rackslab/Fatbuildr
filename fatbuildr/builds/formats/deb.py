#!/usr/bin/env python3
#
# Copyright (C) 2021 Rackslab
#
# This file is part of Fatbuildr.
#
# Fatbuildr is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Fatbuildr is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Fatbuildr.  If not, see <https://www.gnu.org/licenses/>.

import mimetypes
import tarfile
import shutil
import os

from .. import ArtifactEnvBuild
from ...utils import tar_subdir
from ...log import logr

logger = logr(__name__)


class ArtifactBuildDeb(ArtifactEnvBuild):
    """Class to manipulation build of package in Deb format."""

    def __init__(
        self,
        task_id,
        place,
        instance,
        format,
        distribution,
        architectures,
        derivative,
        artifact,
        user_name,
        user_email,
        message,
        tarball,
        src_tarball,
    ):
        super().__init__(
            task_id,
            place,
            instance,
            format,
            distribution,
            architectures,
            derivative,
            artifact,
            user_name,
            user_email,
            message,
            tarball,
            src_tarball,
        )

    @property
    def tarball_ext(self):
        # Dicts to map mimetype encoding to tarfile.open() options and orig
        # symlink source extension.
        exts = {
            'bzip2': 'bz2',
            'gzip': 'gz',
            'xz': 'xz',
        }
        return exts[mimetypes.guess_type(str(self.tarball))[1]]

    def build(self):
        self._build_src()
        for architecture in self.architectures:
            self._build_bin(architecture)

    def _build_src(self):
        """Build deb source package."""

        logger.info(
            "Building source Deb packages for %s",
            self.artifact,
        )

        # Add distribution release tag to targeted version
        self.version.dist = self.instance.pipelines.dist_tag(self.distribution)

        # extract tarball in build place
        logger.debug("Extracting tarball %s in %s", self.tarball, self.place)
        tar = tarfile.open(self.tarball, 'r:' + self.tarball_ext)
        tarball_subdir = self.place.joinpath(tar_subdir(tar))
        tar.extractall(path=self.place)
        tar.close()

        # copy debian dir
        deb_code_from = self.place.joinpath('deb')
        deb_code_to = tarball_subdir.joinpath('debian')
        logger.debug(
            "Copying debian packaging code from %s into %s",
            deb_code_from,
            deb_code_to,
        )
        shutil.copytree(deb_code_from, deb_code_to)

        # Generate patches tree if patches are provided

        if self.has_patches:
            logger.info("Generating debian patches tree")

            patches = self.patches
            patches_to = tarball_subdir.joinpath('debian', 'patches')

            # Create debian patches subdir
            patches_to.mkdir()
            patches_to.chmod(0o755)

            # Move patches in debian patches subdir
            for patch in patches:
                patch.rename(patches_to.joinpath(patch.name))

            # Generate patches series file
            logger.debug("Generating patches series files with patches")
            with open(patches_to.joinpath('series'), 'w+') as fh:
                fh.writelines([path.name + '\n' for path in patches])

        # Check if existing source package and get version
        existing_version = self.registry.source_version(
            self.distribution, self.derivative, self.artifact
        )
        if existing_version:
            logger.info(
                "Found existing version %s, extracting changelog file",
                existing_version.full,
            )
            # extract existing source package changelog
            with open(tarball_subdir.joinpath('debian/changelog'), 'wb+') as fh:
                fh.write(
                    self.registry.source_changelog(
                        self.distribution, self.derivative, self.artifact
                    )
                )

            # Compare existing version with the target version
            if existing_version == self.version:
                logger.info(
                    "Incrementing build number of existing version %s",
                    existing_version.full,
                )
                # increment build ID above the existing version
                self.version.build = existing_version.build + 1

        # Add the new entry to the changelog
        logger.info("Adding entry to changelog")
        cmd = [
            'debchange',
            '--package',
            self.artifact,
            '--newversion',
            self.version.full,
            '--distribution',
            self.distribution,
            '--force-distribution',
            self.message,
        ]

        # If the changelog does not exist yet (ie. not extracted from existing
        # source package), add create argument to ask debchanges for changelog
        # file creation.
        if not existing_version:
            cmd.insert(1, '--create')

        _envs = ['DEBEMAIL=' + self.email, 'DEBFULLNAME=' + self.user]
        self.cruncmd(cmd, chdir=tarball_subdir, envs=_envs)

        #  add symlink to tarball
        orig_tarball_path = self.place.joinpath(
            f"{self.artifact}_{self.version.main}.orig.tar.{self.tarball_ext}",
        )
        logger.debug(
            "Creating symlink %s → %s",
            orig_tarball_path,
            self.tarball,
        )
        orig_tarball_path.symlink_to(self.tarball)

        # build source package
        logger.info("Building source package")
        cmd = ['dpkg-source', '--build', tarball_subdir]
        self.cruncmd(cmd, chdir=str(self.place))

    def _build_bin(self, architecture):
        """Build deb packages binary package."""

        env = self.instance.images_mgr.build_env(
            self.format, self.env_name, architecture
        )
        logger.info(
            "Building binary Deb packages for %s in build environment %s",
            self.artifact,
            env,
        )

        # Save keyring in build place to cowbuilder can check signatures of
        # fatbuildr repositories.
        keyring_path = self.place.joinpath('keyring.asc')
        with open(keyring_path, 'w+') as fh:
            fh.write(self.instance.keyring.export())

        dsc_path = self.place.joinpath(
            self.artifact + '_' + self.version.full + '.dsc'
        )
        cmd = [
            'cowbuilder',
            '--build',
            '--hookdir',
            self.image.format_libdir.joinpath('hooks'),
            '--distribution',
            self.distribution,
            '--bindmounts',
            str(self.place),  # for local repos keyring
            '--basepath',
            env.path,
            '--buildresult',
            str(self.place),
            dsc_path,
        ]

        # The deb registry does not exist until the first artifact is actually
        # published. If it exists, bind-mount so the local repos can be used
        # in cowbuilder environments.
        if self.registry.exists:
            cmd[6:6] = ['--bindmounts', self.registry.path]

        # BUILDRESULT{UID,GID} environments variables are used by pbuilder. When
        # defined, it chowns the build results to this UID/GID. As pbuilder is
        # run as root in container, this mechanism is used to make fatbuildrd
        # user ownership of build results, when build is successful.

        self.cruncmd(
            cmd,
            envs=[
                f"FATBUILDR_REPO={self.registry.path}",
                f"FATBUILDR_KEYRING={keyring_path}",
                f"FATBUILDR_SOURCE={self.instance.name}",
                f"FATBUILDR_DERIVATIVES={' '.join(self.derivatives[::-1])}",
                f"BUILDRESULTUID={os.getuid()}",
                f"BUILDRESULTGID={os.getgid()}",
            ],
        )
