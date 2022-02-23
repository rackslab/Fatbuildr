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

import os
import tempfile
import hashlib
import shutil
import tarfile
from pathlib import Path

import requests

from ..tasks import RunnableTask
from ..cleanup import CleanupRegistry
from ..artefact import ArtefactDefs
from ..cache import CacheArtefact
from ..containers import ContainerRunner
from ..images import Image, BuildEnv
from ..utils import runcmd
from ..log import logr

logger = logr(__name__)


class ArtefactBuild(RunnableTask):
    """Generic parent class of all ArtefactBuild formats."""

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
        super().__init__('artefact build', task_id, place, instance)
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
        self.container = ContainerRunner(conf.containers)
        self.image = Image(conf, self.instance.id, self.format)
        # Get the build environment corresponding to the distribution
        build_env = self.instance.pipelines.dist_env(self.distribution)
        logger.debug(
            "Build environment selected for distribution %s: %s",
            self.distribution,
            build_env,
        )
        self.env = BuildEnv(conf, self.image, build_env)
        self.defs = None  # loaded in prepare()

    def __getattr__(self, name):
        # try in defs
        try:
            return getattr(self.defs, name)
        except AttributeError:
            raise AttributeError(
                "%s does not have %s attribute"
                % (self.__class__.__name__, name)
            )

    @property
    def version(self):
        return self.defs.version(self.derivative)

    @property
    def release(self):
        return self.defs.release(self.format)

    @property
    def has_buildargs(self):
        return self.defs.has_buildargs(self.format)

    @property
    def buildargs(self):
        return self.defs.buildargs(self.format)

    @property
    def fullversion(self):
        return self.defs.fullversion(self.format, self.derivative)

    @property
    def upstream_tarball(self):
        return self.defs.tarball(self)

    @property
    def checksum_format(self):
        return self.defs.checksum_format(self.derivative)

    @property
    def checksum_value(self):
        return self.defs.checksum_value(self.derivative)

    def run(self):
        """Run the build! This is the entry point for fatbuildrd."""
        logger.info("Running build %s" % (self.id))
        try:
            self.prepare()
            self.build()
            self.registry.publish(self)
        except RuntimeError as err:
            logger.error("error during build of %s: %s" % (self.id, err))
            logger.info("Build failed")
        else:
            logger.info("Build succeeded")

    @staticmethod
    def hasher(hash_format):
        """Return the hashlib object corresponding to the hash_format."""
        if hash_format == 'sha1':
            return hashlib.sha1()
        elif hash_format == 'sha256':
            return hashlib.sha256()
        else:
            raise RuntimeError("Unsupported hash format %s" % (hash_format))

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

        if not self.defs.has_tarball:
            # This artefact does not need upstream tarball, nothing more to do
            # here
            return

        if self.cache.has_tarball:
            # The upstream tarball if already in cache, nothing more to do here
            return

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
                "%s checksum do not match: %s != %s"
                % (
                    self.checksum_format,
                    tarball_hash.hexdigest(),
                    self.checksum_value,
                )
            )

    def runcmd(self, cmd, **kwargs):
        """Run command locally and log output in build log file."""
        runcmd(cmd, log=self.log, **kwargs)

    def contruncmd(self, cmd, **kwargs):
        """Run command in container and log output in build log file."""
        _binds = [str(self.place), self.cache.dir]
        # Before the first artefact is actually published, the registry does
        # not exist. Then check it really exists, then bind-mount it.
        if self.registry.exists:
            _binds.append(self.registry.path)
        self.container.run(
            self.image, cmd, binds=_binds, log=self.log, **kwargs
        )
