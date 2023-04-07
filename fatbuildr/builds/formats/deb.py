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

from .. import ArtifactEnvBuild, ArtifactSourceArchive
from ...utils import current_user, extract_artifact_sources_archives
from ...log import logr

logger = logr(__name__)


class ArtifactBuildDeb(ArtifactEnvBuild):
    """Class to manipulation build of package in Deb format."""

    def __init__(
        self,
        task_id,
        user,
        place,
        instance,
        format,
        distribution,
        architectures,
        derivative,
        artifact,
        author,
        email,
        message,
        tarball,
        sources,
        interactive,
    ):
        super().__init__(
            task_id,
            user,
            place,
            instance,
            format,
            distribution,
            architectures,
            derivative,
            artifact,
            author,
            email,
            message,
            tarball,
            sources,
            interactive,
        )

    def tarball_ext(self, path):
        # Dicts to map mimetype encoding to tarfile.open() options and orig
        # symlink source extension.
        exts = {
            'bzip2': 'bz2',
            'gzip': 'gz',
            'xz': 'xz',
        }
        return exts[mimetypes.guess_type(str(path))[1]]

    def supp_tarball_path(self, subdir):
        """Returns the path to the supplementary tarball for the given
        subdir."""
        return self.place.joinpath(
            f"{self.artifact}_{self.version.main}.orig-"
            f"{self.prescript_supp_subdir_renamed(subdir)}.tar.xz",
        )

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

        # Deb source packages do not support source archives in zip format, then
        # first convert all source archives in zip format to tarballs.
        for archive in self.archives:
            if archive.is_zip:
                tarball_path = self.place.joinpath(
                    archive.path.stem + '.tar.xz'
                )
                archive.convert_tar(tarball_path)

        main_tarball_subdir = extract_artifact_sources_archives(
            self.place,
            self.artifact,
            self.main_archive,
            self.other_archives + self.prescript_tarballs,
        )

        # copy debian dir
        deb_code_from = self.place.joinpath('deb')
        deb_code_to = main_tarball_subdir.joinpath('debian')
        logger.debug(
            "Copying debian packaging code from %s into %s",
            deb_code_from,
            deb_code_to,
        )
        shutil.copytree(deb_code_from, deb_code_to)

        # Generate patches tree if patches are provided

        if not self.patches_dir.empty:
            logger.info("Generating debian patches tree")

            patches_to = main_tarball_subdir.joinpath('debian', 'patches')

            # If the patches directory destination path already exists, remove
            # it recursively, artifact patches have more priority.
            if patches_to.exists():
                logger.warning(
                    "Removing existing deb patches directory %s", patches_to
                )
                shutil.rmtree(patches_to)
            # Create debian patches subdir
            patches_to.mkdir()
            patches_to.chmod(0o755)

            # Move patches in debian patches subdir
            for patch in self.patches:
                patch.rename(patches_to.joinpath(patch.name))

            # Generate patches series file
            logger.debug("Generating patches series files with patches")
            with open(patches_to.joinpath('series'), 'w+') as fh:
                fh.writelines([path.name + '\n' for path in self.patches])

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
            with open(
                main_tarball_subdir.joinpath('debian/changelog'), 'wb+'
            ) as fh:
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

        _envs = ['DEBEMAIL=' + self.email, 'DEBFULLNAME=' + self.author]
        self.cruncmd(cmd, chdir=main_tarball_subdir, envs=_envs)

        # Create orig symlinks to upstream source archives
        for archive in self.archives:
            if archive.is_main(self.artifact):
                orig_tarball_path = self.place.joinpath(
                    f"{self.artifact}_{self.version.main}.orig.tar"
                    f".{self.tarball_ext(archive.path)}",
                )
            else:
                orig_tarball_path = self.place.joinpath(
                    f"{self.artifact}_{self.version.main}.orig-"
                    f"{archive.sanitized_stem}.tar"
                    f".{self.tarball_ext(archive.path)}",
                )
            # If the artifact source tarball is in the build place, create a
            # relative symbolic link, so the link stays valid when the task is
            # moved in archives. Otherwise (ie. the tarball is in cache), use
            # the absolute path.
            if self.archive_in_build_place(archive):
                dest = archive.path.relative_to(archive.path.parent)
            else:
                dest = archive.path
            logger.debug(
                "Creating symlink %s → %s",
                orig_tarball_path,
                dest,
            )
            orig_tarball_path.symlink_to(dest)

        # build source package
        logger.info("Building source package")
        cmd = ['dpkg-source', '--build', main_tarball_subdir]
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

        dsc_path = self.place.joinpath(
            self.artifact + '_' + self.version.full + '.dsc'
        )
        # The dpkg-genchanges -sa option is used to force inclusion of source
        # tarball in resulting changes, even when the upstream version is not
        # bumped, because the build can include new version supplementary
        # tarballs generated with prescript. It is safer to ensure the sources
        # are included in changes file for every builds.
        cmd = [
            self.image.builder,
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
            '--debbuildopts=-sa',
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
            asroot=True,  # cowbuilder must be run as root
            envs=[
                f"FATBUILDR_REPO={self.registry.path}",
                f"FATBUILDR_KEYRING={self.build_keyring}",
                f"FATBUILDR_SOURCE={self.instance.name}",
                f"FATBUILDR_DERIVATIVES={' '.join(self.derivatives[::-1])}",
                f"FATBUILDR_INTERACTIVE={'yes' if self.io.interactive else 'no'}",
                f"BUILDRESULTUID={os.getuid()}",
                f"BUILDRESULTGID={os.getgid()}",
            ],
        )

    def prescript_in_env(self, archive_subdir):
        """Execute prescript in Deb build environment using cowbuilder."""
        logger.info(
            "Executing prescript in deb build environment %s",
            self.native_env.name,
        )

        cmd = [
            self.image.builder,
            '--execute',
            '--hookdir',
            self.image.format_libdir.joinpath('hooks'),
            '--distribution',
            self.distribution,
            '--bindmounts',
            str(self.place),
            '--bindmounts',
            self.image.common_libdir,
            '--bindmounts',
            self.registry.path,
            '--basepath',
            self.native_env.path,
            '--',
            self.image.common_libdir.joinpath('pre-stage1-deb.sh'),
            self.prewrapper_path,
            self.prescript_path,
        ]

        self.cruncmd(
            cmd,
            asroot=True,  # cowbuilder must be run as root
            # All these environments variables are consumed by pre-deb-stage1.sh
            # and pre-wrapper.sh scripts, and also by F10derivatives cowbuilder
            # hook, to prepare the environment for the prescript.
            envs=[
                f"FATBUILDR_REPO={self.registry.path}",
                f"FATBUILDR_KEYRING={self.build_keyring}",
                f"FATBUILDR_SOURCE={self.instance.name}",
                f"FATBUILDR_PRESCRIPT_DEPS={' '.join(self.prescript_deps)}",
                f"FATBUILDR_DERIVATIVES={' '.join(self.derivatives[::-1])}",
                f"FATBUILDR_SOURCE_DIR={archive_subdir}",
                f"FATBUILDR_USER={current_user()[1]}",
                f"FATBUILDR_UID={os.getuid()}",
                f"FATBUILDR_GID={os.getgid()}",
            ],
        )
