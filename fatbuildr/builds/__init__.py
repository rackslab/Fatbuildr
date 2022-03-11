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
import hashlib
import shutil
import tarfile
from pathlib import Path

import requests

from ..protocols.exports import ExportableTaskField

from ..tasks import RunnableTask
from ..cleanup import CleanupRegistry
from ..artefact import ArtefactDefs
from ..registry.formats import ArtefactVersion
from ..cache import CacheArtefact
from ..log import logr

logger = logr(__name__)


class ArtefactBuild(RunnableTask):
    """Generic parent class of all ArtefactBuild formats."""

    TASK_NAME = 'artefact build'
    EXFIELDS = {
        ExportableTaskField('format'),
        ExportableTaskField('distribution'),
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
        conf,
        format,
        distribution,
        derivative,
        artefact,
        user_name,
        user_email,
        message,
        tarball,
    ):
        super().__init__(task_id, place, instance)
        self.format = format
        self.distribution = distribution
        self.derivative = derivative
        self.artefact = artefact
        self.user = user_name
        self.email = user_email
        self.message = message
        self.input_tarball = Path(tarball)
        self.cache = CacheArtefact(conf, self.instance.id, self)
        self.registry = self.instance.registry_mgr.factory(self.format)
        # Get the recursive list of derivatives extended by the given
        # derivative.
        self.derivatives = self.instance.pipelines.recursive_derivatives(
            self.derivative
        )
        self.image = self.instance.images_mgr.image(self.format)
        # Get the build environment corresponding to the distribution
        build_env = self.instance.pipelines.dist_env(self.distribution)
        logger.debug(
            "Build environment selected for distribution %s: %s",
            self.distribution,
            build_env,
        )
        self.env = self.instance.images_mgr.build_env(self.format, build_env)
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
    def upstream_tarball(self):
        return self.defs.tarball(self.version.main)

    @property
    def checksum_format(self):
        return self.defs.checksum_format(self.derivative)

    @property
    def checksum_value(self):
        return self.defs.checksum_value(self.derivative)

    def run(self):
        logger.info("Running build %s", self.id)
        self.prepare()
        self.build()
        self.registry.publish(self)

    @staticmethod
    def hasher(hash_format):
        """Return the hashlib object corresponding to the hash_format."""
        if hash_format == 'sha1':
            return hashlib.sha1()
        elif hash_format == 'sha256':
            return hashlib.sha256()
        else:
            raise RuntimeError(f"Unsupported hash format {hash_format}")

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

        # define targeted version
        self.version = ArtefactVersion(
            f"{self.defs.version(self.derivative)}-{self.defs.release(self.format)}"
        )

        if not self.defs.has_tarball:
            # This artefact does not need upstream tarball, nothing more to do
            # here
            return

        if not self.cache.has_tarball:
            #  actual download and write in cache
            dl = requests.get(self.upstream_tarball, allow_redirects=True)
            open(self.cache.tarball_path, 'wb').write(dl.content)

            # verify checksum after download
            with open(self.cache.tarball_path, "rb") as fh:
                tarball_hash = ArtefactBuild.hasher(self.checksum_format)
                while chunk := fh.read(8192):
                    tarball_hash.update(chunk)

            if tarball_hash.hexdigest() != self.checksum_value:
                raise RuntimeError(
                    f"{self.checksum_format} checksum do not match: "
                    f"{tarball_hash.hexdigest()} != {self.checksum_value}"
                )

        # Handle pre script if present
        pre_script_path = self.place.joinpath('pre.sh')
        if pre_script_path.exists():
            logger.info("Pre script is present, modifying the upstream tarball")

            # Create temporary upstream directory
            upstream_dir = self.place.joinpath('upstream')
            upstream_dir.mkdir()

            # Extract original upstream tarball (and get the subdir)
            with tarfile.open(self.cache.tarball_path) as tar:
                tar.extractall(upstream_dir)
                old_tarball_subdir = upstream_dir.joinpath(
                    self._tar_subdir(tar)
                )

            # Run pre script in archives directory using the wrapper
            wrapper_path = self.image.common_libdir.joinpath('pre-wrapper.sh')
            cmd = ['/bin/bash', wrapper_path, pre_script_path]
            self.cruncmd(cmd, chdir=old_tarball_subdir)

            # Increment main version
            self.version.main += '+mod'

            # rename tarball sub-directory to match new archive name
            new_tarball_subdir = upstream_dir.joinpath(
                f"{self.artefact}-{self.version.main}"
            )
            old_tarball_subdir.rename(new_tarball_subdir)

            # Generate the new modified tarball
            mod_tarball_path = self.place.joinpath(
                f"{self.artefact}-{self.version.main}.tar.xz"
            )
            logger.info("Generating modified tarball %s", mod_tarball_path)
            with tarfile.open(mod_tarball_path, 'w:xz') as tar:
                tar.add(
                    new_tarball_subdir,
                    arcname=new_tarball_subdir.relative_to(upstream_dir),
                )
            self.tarball = mod_tarball_path

            # Remove temporary upstream directory
            shutil.rmtree(upstream_dir)
        else:
            logger.info("Artefact tarball is %s", self.cache.tarball_path)
            self.tarball = self.cache.tarball_path

    def cruncmd(self, cmd, **kwargs):
        """Run command in container and log output in build log file."""
        _binds = [self.place, self.cache.dir]
        # Before the first artefact is actually published, the registry does
        # not exist. Then check it really exists, then bind-mount it.
        if self.registry.exists:
            _binds.append(self.registry.path)
        super().cruncmd(self.image, cmd, init=False, binds=_binds, **kwargs)

    @staticmethod
    def _tar_subdir(tar):
        """Returns the name of the subdirectory of the root of the given
        tarball, or raise RuntimeError if not found."""
        subdir = tar.getmembers()[0]
        if not subdir.isdir():
            raise RuntimeError(
                f"unable to define tarball {tar.name} subdirectory"
            )
        return subdir.name
