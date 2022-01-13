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
import subprocess
import logging

import requests

from ..cleanup import CleanupRegistry
from ..pipelines import ArtefactDefs
from ..cache import CacheArtefact
from ..containers import ContainerRunner
from ..images import Image, BuildEnv

logger = logging.getLogger(__name__)


class BuilderArtefact(ArtefactDefs):
    """Generic parent class of all BuilderArtefact formats."""

    def __init__(self, conf, form, registry):
        super().__init__(form.build_dir, form.artefact, form.format)
        self.conf = conf
        self.name = form.artefact
        self.source = form.source
        self.distribution = form.distribution
        self.id = form.id
        self.state = form.state
        self.user = form.user
        self.email = form.email
        self.msg = form.message
        self.tmpdir = form.build_dir
        self.logfile = os.path.join(self.tmpdir, 'build.log')
        self.cache = CacheArtefact(conf, self)
        self.registry = registry(conf, form.distribution)
        self.container = ContainerRunner(conf.containers)
        self.image = Image(conf, form.format)
        self.env = BuildEnv(conf, self.image, form.environment)

    def run(self):
        """Run the build! This is the entry point for fatbuildrd."""
        logger.info("Running build %s" % (self.id))

        handler = logging.FileHandler(self.logfile)
        logging.getLogger().addHandler(handler)

        try:
            self.prepare()
            self.build()
            self.registry.publish(self)
        except RuntimeError as err:
            logger.error("error during build of %s: %s" % (self.id, err))
            logger.info("Build failed")
        else:
            logger.info("Build succeeded")

        logging.getLogger().removeHandler(handler)

    def watch(self):
        """Watch build log file."""
        if self.state == 'finished':
            # dump full build log
            log_path = os.path.join(self.tmpdir, 'build.log')
            with open(log_path, 'r') as fh:
                while chunk := fh.read(8192):
                    try:
                        print(chunk, end='')
                    except BrokenPipeError:
                        # Stop here if hit a broken pipe. It could happen when
                        # watch is given to head for example.
                        break
        else:
            # Follow the log file. It has been choosen to exec `tail -f`
            # because python lacks well maintained and common inotify library.
            # This tail command is in coreutils and it is installed basically
            # everywhere.
            cmd = ['tail', '--follow', self.logfile]
            try:
                subprocess.run(cmd)
            except KeyboardInterrupt:
                # Leave gracefully after a keyboard interrupt (eg. ^c)
                logger.debug("Received keyboard interrupt, leaving.")

    @staticmethod
    def hasher(hash_format):
        """Return the hashlib object corresponding to the hash_format."""
        if hash_format == 'sha1':
            return hashlib.sha1()
        else:
            raise RuntimeError("Unsupported hash format %s" % (hash_format))

    def prepare(self):
        """Download the package upstream tarball and verify checksum if not
           present in cache."""

        if self.cache.has_tarball:
            # nothing to do here
            return

        # ensure artefact cache directory exists
        self.cache.ensure()

        # actual download and write in cache
        dl = requests.get(self.tarball, allow_redirects=True)
        open(self.cache.tarball_path, 'wb').write(dl.content)

        # verify checksum after download
        with open(self.cache.tarball_path, "rb") as fh:
            tarball_hash = BuilderArtefact.hasher(self.checksum_format)
            while chunk := fh.read(8192):
                tarball_hash.update(chunk)

        if tarball_hash.hexdigest() != self.checksum_value:
            raise RuntimeError("%s checksum do not match: %s != %s" \
                               % (self.checksum_format,
                                  tarball_hash.hexdigest(),
                                  self.checksum_value))

    def runcmd(self, cmd, **kwargs):
        """Run command locally and log output in build log file."""
        logger.debug("run cmd: %s" % (' '.join(cmd)))
        with open(self.logfile, 'a') as fh:
            proc = subprocess.run(cmd, **kwargs, stdout=fh, stderr=fh)
            if proc.returncode:
                raise RuntimeError("Command failed with exit code %d: %s" \
                                   % (proc.returncode, ' '.join(cmd)))

    def contruncmd(self, cmd, **kwargs):
        """Run command in container and log output in build log file."""
        _binds = [self.tmpdir, self.cache.dir]
        self.container.run(self.image, cmd, **kwargs, binds=_binds,
                           logfile=self.logfile)
