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

import tempfile
import shutil
import tarfile
from pathlib import Path

from ..protocols.exports import ExportableTaskField

from ..tasks import RunnableTask
from ..cleanup import CleanupRegistry
from ..artifact import ArtifactDefsFactory
from ..registry.formats import ArtifactVersion
from ..git import GitRepository
from ..utils import (
    dl_file,
    verify_checksum,
    tar_subdir,
    current_user,
)
from ..log import logr

logger = logr(__name__)


class ArtifactBuild(RunnableTask):
    """Generic parent class of all ArtifactBuild formats."""

    TASK_NAME = 'artifact build'
    EXFIELDS = {
        ExportableTaskField('format'),
        ExportableTaskField('distribution'),
        ExportableTaskField('architectures', list[str]),
        ExportableTaskField('derivative'),
        ExportableTaskField('artifact'),
        ExportableTaskField('user'),
        ExportableTaskField('email'),
        ExportableTaskField('message'),
    }

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
        super().__init__(task_id, place, instance)
        self.format = format
        self.distribution = distribution
        self.architectures = architectures
        self.derivative = derivative
        self.artifact = artifact
        self.user = user_name
        self.email = user_email
        self.message = message
        self.input_tarball = Path(tarball)
        self.src_tarball = Path(src_tarball) if src_tarball else None
        self.cache = self.instance.cache.artifact(self)
        self.registry = self.instance.registry_mgr.factory(self.format)
        # Get the recursive list of derivatives extended by the given
        # derivative.
        self.derivatives = self.instance.pipelines.recursive_derivatives(
            self.derivative
        )
        self.image = self.instance.images_mgr.image(self.format)
        self.defs = None  # loaded in prepare()
        self.version = None  # initialized in prepare(), after defs are loaded
        # Path the upstream tarball, initialized in prepare(), after optional
        # pre-script is processed.
        self.tarball = None

    def __getattr__(self, name):
        # try in defs
        try:
            return getattr(self.defs, name)
        except AttributeError:
            raise AttributeError(
                f"{self.__class__.__name__} does not have {name} attribute"
            )

    @property
    def tarball_url(self):
        return self.defs.tarball_url(self.version.main)

    @property
    def tarball_filename(self):
        return self.defs.tarball_filename(self.version.main)

    @property
    def checksum_format(self):
        return self.defs.checksum_format(self.derivative)

    @property
    def checksum_value(self):
        return self.defs.checksum_value(self.derivative)

    @property
    def patches_dir(self):
        """Returns the Path to the artifact patches directory."""
        return self.place.joinpath('patches', self.version.main)

    @property
    def patches(self):
        """Returns the sorted list of Path of patches found in artifact patches
        directory."""
        return sorted([item for item in self.patches_dir.iterdir()])

    @property
    def has_patches(self):
        """Returns True if artifact patches directory exists, False
        otherwise."""
        return self.patches_dir.exists()

    def run(self):
        logger.info("Running build %s", self.id)
        self.prepare()
        self.build()
        self.registry.publish(self)

    def prepare(self):
        """Extract input tarball and, if not present in cache, download the
        package upstream tarball and verify its checksum."""

        # Extract artifact tarball in build place
        logger.info(
            "Extracting tarball %s in destination %s",
            self.input_tarball,
            self.place,
        )
        tar = tarfile.open(self.input_tarball, 'r:xz')
        tar.extractall(path=self.place)
        tar.close()

        # Remove the input tarball
        self.input_tarball.unlink()

        # ensure artifact cache directory exists
        self.cache.ensure()

        # load defs
        self.defs = ArtifactDefsFactory.get(
            self.place, self.artifact, self.format
        )

        if self.src_tarball:
            # If source tarball has been provided with the build request, use it.
            src_tarball_target = self.place.joinpath(self.src_tarball.name)
            logger.info("Using provided source tarball %s", src_tarball_target)
            # Move the source tarball in build place. The shutil module is used
            # here to support file move between different filesystems.
            # Unfortunately, PurePath.rename() does not support this case.
            shutil.move(self.src_tarball, src_tarball_target)

            # The main version of the artifact is extracted from the the source
            # tarball name, it is prefixed by artifact name followed by
            # underscore, it is suffixed by the extension'.tar.xz'.
            main_version_str = self.src_tarball.name[
                len(self.artifact) + 1 : -7
            ]
            logger.debug(
                "Artifact main version extracted from source tarball name: %s",
                main_version_str,
            )
            self.version = ArtifactVersion(
                f"{main_version_str}-{self.defs.release}"
            )
            self.tarball = src_tarball_target
        elif not self.defs.has_tarball:
            # This artifact is not defined with an upstream tarball URL and the
            # user did not provide source tarball within the build request. This
            # case happens for OSI format for example. The only thing to do here
            # is defining the targeted version.
            self.version = ArtifactVersion(
                f"{self.defs.version(self.derivative)}-{self.defs.release}"
            )
            return
        else:
            # If the source tarball has not been provided and the artifact is
            # defined with a source tarball URL, it is downloaded in cache (if
            # not already present) using this URL.

            # The targeted version is fully defined based on definition
            self.version = ArtifactVersion(
                f"{self.defs.version(self.derivative)}-{self.defs.release}"
            )
            if not self.cache.has_tarball:
                dl_file(self.tarball_url, self.cache.tarball)

            verify_checksum(
                self.cache.tarball,
                self.checksum_format,
                self.checksum_value,
            )

            logger.info(
                "Using artifact source tarball from cache %s",
                self.cache.tarball,
            )
            self.tarball = self.cache.tarball

        # Handle pre script if present
        pre_script_path = self.place.joinpath('pre.sh')
        if pre_script_path.exists():
            logger.info("Pre script is present, modifying the upstream tarball")

            # Create temporary upstream directory
            upstream_dir = self.place.joinpath('upstream')
            upstream_dir.mkdir()

            # Extract original upstream tarball (and get the subdir)
            with tarfile.open(self.tarball) as tar:
                tar.extractall(upstream_dir)
                tarball_subdir = upstream_dir.joinpath(tar_subdir(tar))

            # init the git repository with its initial commit
            git = GitRepository(tarball_subdir, self.user, self.email)

            # import existing patches in queue
            if self.has_patches:
                git.import_patches(self.patches_dir)

            # Run pre script in archives directory using the wrapper
            wrapper_path = self.image.common_libdir.joinpath('pre-wrapper.sh')
            cmd = ['/bin/bash', wrapper_path, pre_script_path]
            self.cruncmd(
                cmd, chdir=tarball_subdir, user=current_user()[1], readonly=True
            )

            # export git repo diff in patch queue
            git.commit_export(
                self.patches_dir,
                9999,
                'fatbuildr-prescript',
                self.user,
                self.email,
                "Patch generated by artifact pre-script.",
            )

            # Remove temporary upstream directory
            shutil.rmtree(upstream_dir)

    def cruncmd(self, cmd, **kwargs):
        """Run command in container and log output in build log file."""
        _binds = [self.place, self.cache.dir]
        # Before the first artifact is actually published, the registry does
        # not exist. Then check it really exists, then bind-mount it.
        if self.registry.exists:
            _binds.append(self.registry.path)
        super().cruncmd(self.image, cmd, init=False, binds=_binds, **kwargs)


class ArtifactEnvBuild(ArtifactBuild):
    """Abstract class for artifact builds using a build environments in
    container images (eg. deb, rpm)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get the build environment name corresponding to the distribution
        self.env_name = self.instance.pipelines.dist_env(self.distribution)
        logger.debug(
            "Build environment selected for distribution %s: %s",
            self.distribution,
            self.env_name,
        )
