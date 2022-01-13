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
import tarfile
import tempfile
import uuid
import shutil
from datetime import datetime
import logging

import yaml

from .pipelines import PipelinesDefs
from .cleanup import CleanupRegistry

logger = logging.getLogger(__name__)

class BuildForm(object):

    def __init__(self, source, user, email, instance, distribution, environment, fmt, artefact, submission, message):
        self.source = source
        self.user = user
        self.email = email
        self.instance = instance
        self.distribution = distribution
        self.environment = environment
        self.format = fmt
        self.artefact = artefact
        self.submission = submission
        self.message = message

    def todict(self):
        return {
            'source': self.source,
            'user': self.user,
            'email': self.email,
            'instance': self.instance,
            'distribution': self.distribution,
            'environment': self.environment,
            'format': self.format,
            'artefact': self.artefact,
            'submission': int(self.submission.timestamp()),
            'message': self.message
        }

    def save(self, path):
        yml_path = os.path.join(path, 'build.yml')
        logger.debug("Creating YAML build form file %s" % (yml_path))
        with open(yml_path, 'w+') as fh:
            yaml.dump(self.todict(), fh)

    def move(self, src, dest):
        yml_path = os.path.join(src, 'build.yml')
        logger.debug("Moving YAML build form file %s to directory %s" % (yml_path, dest))
        shutil.move(yml_path, dest)

    @classmethod
    def load(cls, path):
        yml_path = os.path.join(path, 'build.yml')
        with open(yml_path, 'r') as fh:
            description = yaml.load(fh, Loader=yaml.FullLoader)
        return cls(description['source'],
                   description['user'],
                   description['email'],
                   description['instance'],
                   description['distribution'],
                   description['environment'],
                   description['format'],
                   description['artefact'],
                   datetime.fromtimestamp(description['submission']),
                   description['message'])


class BuildArchive(object):

    def __init__(self, place, build_id):
        self.form = BuildForm.load(place)
        self.id = build_id
        self.state = 'finished'
        self.build_dir = place


class BuildRequest(object):

    def __init__(self, place, build_id, state, build_dir, *args):

        self.place = place
        self.id = build_id
        self.state = state
        self.build_dir = build_dir

        if isinstance(args[0], BuildForm):
            self.form = args[0]
        else:
            self.form = BuildForm(*args)

    def dump(self):
        print("Build request %s" % (self.id))
        print("  state: %s" % (self.state))
        print("  build_dir: %s" % (self.build_dir))
        print("  source: %s" % (self.form.source))
        print("  user: %s" % (self.form.user))
        print("  email: %s" % (self.form.email))
        print("  instance: %s" % (self.form.instance))
        print("  distribution: %s" % (self.form.distribution))
        print("  environment: %s" % (self.form.environment))
        print("  format: %s" % (self.form.format))
        print("  artefact: %s" % (self.form.artefact))
        print("  submission: %s" % (self.form.submission.isoformat(sep=' ',timespec='seconds')))
        print("  message: %s" % (self.form.message))

    def move_form(self, dest):
        self.form.move(self.place, dest)

    def save_state(self, build_dir):
        state_path = os.path.join(self.place, 'state')
        logger.debug("Creating state file %s" % (state_path))
        with open(state_path, 'w+') as fh:
            fh.write(build_dir)

    def prepare_tarball(self, basedir, dest):
        # create an archive of artefact subdirectory
        artefact_def_path = os.path.join(basedir, self.form.artefact)
        if not os.path.exists(artefact_def_path):
            raise RuntimeError("artefact definition directory %s does not exist" % (artefact_def_path))

        tar_path = os.path.join(dest, 'artefact.tar.xz')
        logger.debug("Creating archive %s with artefact definition directory %s" % (tar_path, artefact_def_path))
        tar = tarfile.open(tar_path, 'x:xz')
        tar.add(artefact_def_path, arcname='.', recursive=True)
        tar.close()

    def extract_tarball(self, dest):
        tar_path = os.path.join(self.place, 'artefact.tar.xz')
        logger.debug("Extracting tarball %s" % (tar_path))
        tar = tarfile.open(tar_path, 'r:xz')
        tar.extractall(path=dest)
        tar.close()

    @classmethod
    def load(cls, place, build_id):
        """Return a BuildRequest loaded from place"""

        state_path = os.path.join(place, 'state')
        if os.path.exists(state_path):
            state = "running"
            with open(state_path) as fh:
                build_dir = fh.read()
        else:
            state = "pending"
            build_dir = None

        return cls(place, build_id, state, build_dir, BuildForm.load(place))


class QueueManager(object):
    """Manage the queue of pending builds."""

    def __init__(self, conf):
        self.conf = conf

    @property
    def empty(self):
        return len(os.listdir(self.conf.dirs.queue)) == 0

    def submit(self):
        # create tmp submission directory
        tmpdir = tempfile.mkdtemp(prefix='fatbuildr', dir=self.conf.dirs.tmp)
        CleanupRegistry.add_tmpdir(tmpdir)
        logger.debug("Created tmp directory %s" % (tmpdir))

        # load pipelines defs to get dist→format/env mapping
        pipelines = PipelinesDefs(self.conf.run.basedir)

        # If the user did not provide a build  message, load the default
        # message from the pipelines definition.
        msg = self.conf.run.build_msg
        if msg is None:
            msg = pipelines.msg

        build_id = str(uuid.uuid4())  # generate build id

        # create build request
        request = BuildRequest(os.path.join(self.conf.dirs.queue, build_id),
                               build_id,
                               'pending',  # initial state
                               None,  # initial build_dir
                               pipelines.name,
                               self.conf.run.user_name,
                               self.conf.run.user_email,
                               self.conf.run.instance,
                               self.conf.run.distribution,
                               pipelines.dist_env(self.conf.run.distribution),
                               pipelines.dist_format(self.conf.run.distribution),
                               self.conf.run.artefact,
                               datetime.now(),
                               msg)

        # save the request form in tmpdir
        request.form.save(tmpdir)

        # prepare artefact tarball
        request.prepare_tarball(self.conf.run.basedir, tmpdir)

        # move tmp build submission directory to request place in queue
        logger.debug("Moving tmp directory %s to %s" % (tmpdir, request.place))
        shutil.move(tmpdir, request.place)
        CleanupRegistry.del_tmpdir(tmpdir)
        logger.info("Build build %s submitted" % (request.id))

        return request.id

    def pick(self):

        request = self._load_requests()[0]

        logger.info("Picking up build request %s from queue" % (request.id))

        return request

    def archive(self, build):

        dest = os.path.join(self.conf.dirs.archives, build.id)
        logger.info("Moving build directory %s to archives directory %s" % (build.place, dest))
        shutil.move(build.place, dest)
        CleanupRegistry.del_tmpdir(build.place)

        build.request.move_form(dest)

        logger.info("Removing build request %s from queue" % (build.id))
        shutil.rmtree(build.request.place)

    def _load_requests(self):
        _requests = []
        for build_id in os.listdir(self.conf.dirs.queue):
            request = BuildRequest.load(os.path.join(self.conf.dirs.queue, build_id), build_id)
            _requests.append(request)
         # Returns build requests sorted by submission timestamps
        _requests.sort(key=lambda build: build.form.submission)
        return _requests

    def dump(self):
        """Print all builds requests in the queue."""
        for request in self._load_requests():
            request.dump()

    def load(self):
        return self._load_requests()

    def get(self, build_id):
        """Return the BuildRequest or the BuildArchive with the build_id in
           argument, looking both in the queue and in the archives."""

        build = None
        if build_id in os.listdir(self.conf.dirs.queue):
            logger.debug("Found build %s in queue" % (build_id))
            build = BuildRequest.load(os.path.join(self.conf.dirs.queue, build_id), build_id)
        elif build_id in os.listdir(self.conf.dirs.archives):
            logger.debug("Found build %s in archives" % (build_id))
            build = BuildArchive(os.path.join(self.conf.dirs.archives, build_id), build_id)
        else:
            raise RuntimeError("Unable to find build %s" % (build_id))

        return build
