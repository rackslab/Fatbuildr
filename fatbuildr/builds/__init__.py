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

import requests

from ..cleanup import CleanupRegistry
from ..artefact import ArtefactDefs
from ..registry.manager import RegistryManager
from ..cache import CacheArtefact
from ..containers import ContainerRunner
from ..images import Image, BuildEnv
from ..keyring import KeyringManager
from ..instances import Instances
from ..log import logr
from .form import BuildForm

logger = logr(__name__)


class AbstractBuild:
    def __init__(self, place, build_id):
        self.form = None
        self.id = build_id
        self.place = place

    @property
    def state(self):
        if isinstance(self, BuildArchive):
            return 'finished'
        elif isinstance(self, BuildSubmission):
            return 'pending'
        elif isinstance(self, ArtefactBuild):
            return 'running'
        else:
            raise RuntimeError("Unsupported instance %s" % (type(self)))

    @property
    def logfile(self):
        if self.place is None or self.state not in ['running', 'finished']:
            return None
        return os.path.join(self.place, 'build.log')

    def __getattr__(self, name):
        """Returns self.form attribute as if they were instance attributes."""
        try:
            return getattr(self.form, name)
        except AttributeError:
            raise AttributeError(
                "%s does not have %s attribute"
                % (self.__class__.__name__, name)
            )


class BuildArchive(AbstractBuild):
    def __init__(self, place, build_id):
        super().__init__(place, build_id)
        self.form = BuildForm.load(place)


class BuildSubmission(AbstractBuild):

    ARCHIVE_FILE = 'artefact.tar.xz'

    def __init__(self, place, build_id, form):
        super().__init__(place, build_id)
        self.form = form

    def transfer_inputs(self, dest):
        """Extract artefact archive and move build form in dest."""

        # Extract artefact tarball in dest
        tar_path = os.path.join(self.place, BuildSubmission.ARCHIVE_FILE)
        logger.debug(
            "Extracting tarball %s in destination %s" % (tar_path, dest)
        )
        tar = tarfile.open(tar_path, 'r:xz')
        tar.extractall(path=dest)
        tar.close()

        # Move build form in dest
        self.form.move(self.place, dest)

    @classmethod
    def load(cls, place, build_id):
        form = BuildForm.load(place)
        return cls(place, build_id, form)

    @classmethod
    def load_from_request(cls, place, request, build_id):
        submission = cls(place, build_id, request.form)
        logger.debug(
            "Moving submission directory %s to %s"
            % (request.place, submission.place)
        )
        shutil.move(request.place, submission.place)
        return submission


class BuildRequest(AbstractBuild):

    ARCHIVE_FILE = 'artefact.tar.xz'

    def __init__(self, place, *args):
        super().__init__(place, None)
        if isinstance(args[0], BuildForm):
            self.form = args[0]
        else:
            self.form = BuildForm(*args)

    @property
    def tarball(self):
        return os.path.join(self.place, BuildRequest.ARCHIVE_FILE)

    @property
    def formfile(self):
        return os.path.join(self.place, self.form.filename)

    def prepare_tarball(self, basedir, subdir, dest):
        # create an archive of artefact subdirectory
        artefact_def_path = os.path.join(basedir, subdir)
        if not os.path.exists(artefact_def_path):
            raise RuntimeError(
                "artefact definition directory %s does not exist"
                % (artefact_def_path)
            )

        tar_path = os.path.join(dest, BuildRequest.ARCHIVE_FILE)
        logger.debug(
            "Creating archive %s with artefact definition directory %s"
            % (tar_path, artefact_def_path)
        )
        tar = tarfile.open(tar_path, 'x:xz')
        tar.add(artefact_def_path, arcname='.', recursive=True)
        tar.close()

    def cleanup(self):
        if not os.path.exists(self.place):
            logger.debug(
                "Request directory %s has already been removed, "
                "nothing to clean up",
                self.place,
            )
            return
        logger.debug("Removing request directory %s", self.place)
        shutil.rmtree(self.place)

    @classmethod
    def load(cls, place):
        return cls(place, BuildForm.load(place))


class ArtefactBuild(AbstractBuild):
    """Generic parent class of all ArtefactBuild formats."""

    def __init__(self, conf, build_id, form):
        self.conf = conf
        self.form = form
        self.name = form.artefact
        self.id = build_id
        self._instance = Instances(self.conf)[self.instance]
        self.place = os.path.join(self.conf.dirs.build, self.id)
        self.cache = CacheArtefact(conf, self.instance, self)
        self.registry = RegistryManager.factory(
            self.format, conf, self.instance
        )
        # Get the recursive list of derivatives extended by the given
        # derivative.
        self.derivatives = self._instance.recursive_derivatives(self.derivative)
        self.container = ContainerRunner(conf.containers)
        self.image = Image(conf, self.instance, self.format)
        self.env = BuildEnv(conf, self.image, self.environment)
        self.keyring = KeyringManager(conf).keyring(self.instance)
        self.keyring.load()
        self.defs = None  # loaded in prepare()

    def __getattr__(self, name):
        # try in form first, then try in defs
        try:
            return getattr(self.form, name)
        except AttributeError:
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
    def tarball(self):
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

        # setup logger to duplicate logs in logfile
        logger.add_file(self.logfile)

        try:
            self.prepare()
            self.build()
            self.registry.publish(self)
        except RuntimeError as err:
            logger.error("error during build of %s: %s" % (self.id, err))
            logger.info("Build failed")
        else:
            logger.info("Build succeeded")

        logger.del_file()

    def init_from_submission(self, submission):

        if os.path.exists(self.place):
            logger.warning("Build directory %s already exists" % (self.place))
        else:
            # create build directory
            logger.debug("Creating build directory %s" % (self.place))
            os.mkdir(self.place)
            os.chmod(self.place, 0o755)  # be umask agnostic

        # get input from requests
        submission.transfer_inputs(self.place)

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
        """Download the package upstream tarball and verify checksum if not
        present in cache."""

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
        dl = requests.get(self.tarball, allow_redirects=True)
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
        logger.debug("run cmd: %s" % (' '.join(cmd)))
        with open(self.logfile, 'a') as fh:
            proc = subprocess.run(cmd, **kwargs, stdout=fh, stderr=fh)
            if proc.returncode:
                raise RuntimeError(
                    "Command failed with exit code %d: %s"
                    % (proc.returncode, ' '.join(cmd))
                )

    def contruncmd(self, cmd, **kwargs):
        """Run command in container and log output in build log file."""
        _binds = [self.place, self.cache.dir]
        # Before the first artefact is actually published, the registry does
        # not exist. Then check it really exists, then bind-mount it.
        if self.registry.exists:
            _binds.append(self.registry.path)
        self.container.run(
            self.image, cmd, **kwargs, binds=_binds, logfile=self.logfile
        )

    @classmethod
    def load_from_submission(cls, conf, submission):
        obj = cls(conf, submission.id, submission.form)
        obj.init_from_submission(submission)
        return obj
