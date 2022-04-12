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
from ..artefact import ArtefactDefs
from ..registry.formats import ArtefactVersion
from ..git import GitRepository
from ..utils import dl_file, verify_checksum, tar_subdir, host_architecture, current_user
from ..log import logr

logger = logr(__name__)


class ArtefactBuild(RunnableTask):
    """Generic parent class of all ArtefactBuild formats."""

    TASK_NAME = 'artefact build'
    EXFIELDS = {
        ExportableTaskField('format'),
        ExportableTaskField('distribution'),
        ExportableTaskField('architectures', list[str]),
        ExportableTaskField('derivative'),
        ExportableTaskField('artefact'),
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
        artefact,
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
        self.artefact = artefact
        self.user = user_name
        self.email = user_email
        self.message = message
        self.input_tarball = Path(tarball)
        self.src_tarball = Path(src_tarball) if src_tarball else None
        self.cache = self.instance.cache.artefact(self)
        self.registry = self.instance.registry_mgr.factory(self.format)
        # Get the recursive list of derivatives extended by the given
        # derivative.
        self.derivatives = self.instance.pipelines.recursive_derivatives(
            self.derivative
        )
        self.image = self.instance.images_mgr.image(self.format)
        # Get the build environment name corresponding to the distribution
        self.env_name = self.instance.pipelines.dist_env(self.distribution)
        logger.debug(
            "Build environment selected for distribution %s: %s",
            self.distribution,
            self.env_name,
        )
        self.host_env = self.instance.images_mgr.build_env(
            self.format, self.env_name, host_architecture()
        )
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
    def has_buildargs(self):
        return self.defs.has_buildargs(self.format)

    @property
    def buildargs(self):
        return self.defs.buildargs(self.format)

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
        """Returns the Path to the artefact patches directory."""
        return self.place.joinpath('patches')

    @property
    def patches(self):
        """Returns the sorted list of Path of patches found in artefact patches
        directory."""
        return sorted([item for item in self.patches_dir.iterdir()])

    @property
    def has_patches(self):
        """Returns True if artefact patches directory exists, False
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

        # Extract artefact tarball in build place
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

        # ensure artefact cache directory exists
        self.cache.ensure()

        # load defs
        self.defs = ArtefactDefs(self.place)

        if self.src_tarball:
            # If source tarball has been provided with the build request, use it.
            src_tarball_target = self.place.joinpath(self.src_tarball.name)
            logger.info("Using provided source tarball %s", src_tarball_target)
            # Move the source tarball in build place. The shutil module is used
            # here to support file move between different filesystems.
            # Unfortunately, PurePath.rename() does not support this case.
            shutil.move(self.src_tarball, src_tarball_target)

            # The main version of the artefact is extract from the the source
            # tarball name, it is prefixed by artefact name followed by
            # underscore, it is suffixed by the extension'.tar.xz'.
            main_version_str = self.src_tarball.name[
                len(self.artefact) + 1 : -7
            ]
            logger.debug(
                "Artefact main version extracted from source tarball name: %s",
                main_version_str,
            )
            self.version = ArtefactVersion(
                f"{main_version_str}-{self.defs.release(self.format)}"
            )
            self.tarball = src_tarball_target
        elif not self.defs.has_tarball:
            # This artefact is not defined with an upstream tarball URL and the
            # user did not provide source tarball within the build request,
            # there is nothing more to do here
            return
        else:
            # If the source tarball has not been provided and the artefact is
            # defined with a source tarball URL, it is downloaded in cache (if
            # not already present) using this URL.

            # The targeted version is fully defined based on definition
            self.version = ArtefactVersion(
                f"{self.defs.version(self.derivative)}-{self.defs.release(self.format)}"
            )
            if not self.cache.has_tarball:
                dl_file(self.tarball_url, self.cache.tarball)
                verify_checksum(
                    self.cache.tarball,
                    self.checksum_format,
                    self.checksum_value,
                )

            logger.info(
                "Using artefact source tarball from cache %s",
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
            self.cruncmd(cmd, chdir=tarball_subdir, user=current_user()[1], readonly=True)

            # export git repo diff in patch queue
            git.commit_export(
                self.patches_dir,
                9999,
                'fatbuildr-prescript',
                self.user,
                self.email,
                "Patch generated by artefact pre-script.",
            )

            # Remove temporary upstream directory
            shutil.rmtree(upstream_dir)

    def cruncmd(self, cmd, **kwargs):
        """Run command in container and log output in build log file."""
        _binds = [self.place, self.cache.dir]
        # Before the first artefact is actually published, the registry does
        # not exist. Then check it really exists, then bind-mount it.
        if self.registry.exists:
            _binds.append(self.registry.path)
        super().cruncmd(self.image, cmd, init=False, binds=_binds, **kwargs)
