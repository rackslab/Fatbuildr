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
import tarfile
import logging

import requests

from ..cleanup import CleanupRegistry
from ..pipelines import ArtefactDefs
from ..cache import CacheArtefact
from ..containers import ContainerRunner
from ..images import Image, BuildEnv
from .form import BuildForm

logger = logging.getLogger(__name__)


class AbstractBuild():

    def __init__(self, place, build_id):
        self.form = None
        self.id = build_id
        self.place = place

    def watch(self):
        raise NotImplementedError()

    @property
    def state(self):
        if isinstance(self, BuildArchive):
            return 'finished'
        elif isinstance(self, BuildRequest):
            return 'pending'
        elif isinstance(self, ArtefactBuild):
            return 'running'
        else:
            raise RuntimeError("Unsupported instance %s" % (type(self)))

    @property
    def logfile(self):
        if self.place is None:
            return None
        return os.path.join(self.place, 'build.log')

    def __getattr__(self, name):
        """Returns self.form attribute as if they were instance attributes."""
        try:
            return getattr(self.form, name)
        except AttributeError:
            raise AttributeError("%s does not have %s attribute" % (self.__class__.__name__, name))

    def dump(self):
        if isinstance(self, BuildArchive):
            print("Build archive %s" % (self.id))
        elif isinstance(self, BuildRequest):
            print("Build request %s" % (self.id))
        elif isinstance(self, ArtefactBuild):
            print("Build %s" % (self.id))
        else:
            raise RuntimeError("Unsupported instance %s" % (type(self)))
        print("  state: %s" % (self.state))
        print("  source: %s" % (self.source))
        print("  user: %s" % (self.user))
        print("  email: %s" % (self.email))
        print("  instance: %s" % (self.instance))
        print("  distribution: %s" % (self.distribution))
        print("  environment: %s" % (self.environment))
        print("  format: %s" % (self.format))
        print("  artefact: %s" % (self.artefact))
        print("  submission: %s" % (self.submission.isoformat(sep=' ',timespec='seconds')))
        print("  message: %s" % (self.message))


class BuildArchive(AbstractBuild):

    def __init__(self, place, build_id):
        super().__init__(place, build_id)
        self.form = BuildForm.load(place)

    def watch(self):
        # dump full build log
        log_path = os.path.join(self.logfile)
        with open(self.logfile, 'r') as fh:
             while chunk := fh.read(8192):
                try:
                    print(chunk, end='')
                except BrokenPipeError:
                    # Stop here if hit a broken pipe. It could happen when
                    # watch is given to head for example.
                    break


class BuildRequest(AbstractBuild):

    ARCHIVE_FILE = 'artefact.tar.xz'

    def __init__(self, place, build_id, *args):
        super().__init__(place, build_id)

        if isinstance(args[0], BuildForm):
            self.form = args[0]
        else:
            self.form = BuildForm(*args)

    def prepare_tarball(self, basedir, dest):
        # create an archive of artefact subdirectory
        artefact_def_path = os.path.join(basedir, self.artefact)
        if not os.path.exists(artefact_def_path):
            raise RuntimeError("artefact definition directory %s does not exist" % (artefact_def_path))

        tar_path = os.path.join(dest, BuildRequest.ARCHIVE_FILE)
        logger.debug("Creating archive %s with artefact definition directory %s" % (tar_path, artefact_def_path))
        tar = tarfile.open(tar_path, 'x:xz')
        tar.add(artefact_def_path, arcname='.', recursive=True)
        tar.close()

    def transfer_inputs(self, dest):
        """Extract artefact archive and move build form in dest."""

        # Extract artefact tarball in dest
        tar_path = os.path.join(self.place, BuildRequest.ARCHIVE_FILE)
        logger.debug("Extracting tarball %s in destination %s" % (tar_path, dest))
        tar = tarfile.open(tar_path, 'r:xz')
        tar.extractall(path=dest)
        tar.close()

        # Move build form in dest
        self.form.move(self.place, dest)

    @classmethod
    def load(cls, place, build_id):
        """Return a BuildRequest loaded from place"""
        return cls(place, build_id, BuildForm.load(place))


class ArtefactBuild(AbstractBuild):
    """Generic parent class of all ArtefactBuild formats."""

    def __init__(self, conf, build_id, form, registry):
        self.conf = conf
        self.form = form
        self.name = form.artefact
        self.id = build_id
        self.place = os.path.join(self.conf.dirs.build, self.id)
        self.cache = CacheArtefact(conf, self)
        self.registry = registry(conf, self.distribution)
        self.container = ContainerRunner(conf.containers)
        self.image = Image(conf, self.format)
        self.env = BuildEnv(conf, self.image, self.environment)
        self.defs = None  # loaded in prepare()

    def __getattr__(self, name):
        # try in form first, then try in defs
        try:
            return getattr(self.form, name)
        except AttributeError:
            try:
                return getattr(self.defs, name)
            except AttributeError:
                raise AttributeError("%s does not have %s attribute" % (self.__class__.__name__, name))

    def run(self):
        """Run the build! This is the entry point for fatbuildrd."""
        logger.info("Running build %s" % (self.id))

        # setup logger to use logfile
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
        """Watch running build log file."""
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

    def init_from_request(self, request):

        if os.path.exists(self.place):
            logger.warning("Build directory %s already exists" % (self.place))
        else:
            # create build directory
            logger.debug("Creating build directory %s" % (self.place))
            os.mkdir(self.place)
            os.chmod(self.place, 0o755)  # be umask agnostic

        # get input from requests
        request.transfer_inputs(self.place)

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

        # load defs
        self.defs = ArtefactDefs(self.place, self.name, self.format)

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
            tarball_hash = ArtefactBuild.hasher(self.checksum_format)
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
        _binds = [self.place, self.cache.dir]
        self.container.run(self.image, cmd, **kwargs, binds=_binds,
                           logfile=self.logfile)

    @classmethod
    def load_from_request(cls, conf, request):
        instance = cls(conf, request.id, request.form)
        instance.init_from_request(request)
        return instance
