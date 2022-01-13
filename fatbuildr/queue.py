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

    def __init__(self, source, user, email, instance, distribution, environment, fmt, artefact, submission, message, id=str(uuid.uuid4()), state='pending', build_dir=None):
        self.id = id
        self.state = state
        self.build_dir = build_dir
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

    def dump(self):
        print("Build %s" % (self.id))
        print("  state: %s" % (self.state))
        print("  build_dir: %s" % (self.build_dir))
        print("  source: %s" % (self.source))
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

    @classmethod
    def fromyaml(cls, id, state, build_dir, stream):
        description = yaml.load(stream, Loader=yaml.FullLoader)
        return cls(description['source'],
                   description['user'],
                   description['email'],
                   description['instance'],
                   description['distribution'],
                   description['environment'],
                   description['format'],
                   description['artefact'],
                   datetime.fromtimestamp(description['submission']),
                   description['message'],
                   id=id,
                   state=state,
                   build_dir=build_dir)


class QueueManager(object):
    """Manage the queue of pending builds."""

    def __init__(self, conf):
        self.conf = conf

    def submit(self):
        # create tmp submission directory
        tmpdir = tempfile.mkdtemp(prefix='fatbuildr', dir=self.conf.dirs.tmp)
        CleanupRegistry.add_tmpdir(tmpdir)
        logger.debug("Created tmp directory %s" % (tmpdir))

        # load pipelines defs to get dist→format/env mapping
        pipelines = PipelinesDefs(self.conf.run.basedir)

        # create an archive of artefact subdirectory
        artefact_def_path = os.path.join(self.conf.run.basedir,
                                         self.conf.run.artefact)
        if not os.path.exists(artefact_def_path):
            raise RuntimeError("artefact definition directory %s does not exist" % (artefact_def_path))

        tar_path = os.path.join(tmpdir, 'artefact.tar.xz')
        logger.debug("Creating archive %s with artefact definition directory %s" % (tar_path, artefact_def_path))
        tar = tarfile.open(tar_path, 'x:xz')
        tar.add(artefact_def_path, arcname='.', recursive=True)
        tar.close()

        # If the user did not provide a build  message, load the default
        # message from the pipelines definition.
        msg = self.conf.run.build_msg
        if msg is None:
            msg = pipelines.msg

        # create yaml build form
        form = BuildForm(pipelines.name,
                         self.conf.run.user_name,
                         self.conf.run.user_email,
                         self.conf.run.instance,
                         self.conf.run.distribution,
                         pipelines.dist_env(self.conf.run.distribution),
                         pipelines.dist_format(self.conf.run.distribution),
                         self.conf.run.artefact,
                         datetime.now(),
                         msg)

        yml_path = os.path.join(tmpdir, 'build.yml')
        logger.debug("Creating YAML build form file %s" % (yml_path))
        with open(yml_path, 'w+') as fh:
            yaml.dump(form.todict(), fh)

        # move tmp build submission directory in queue
        dest = os.path.join(self.conf.dirs.queue, form.id)
        logger.debug("Moving tmp directory %s to %s" % (tmpdir, dest))
        shutil.move(tmpdir, dest)
        CleanupRegistry.del_tmpdir(tmpdir)
        logger.info("Build build %s submited" % (form.id))

        return form.id

    def pick(self, form):

        logger.info("Picking up build %s from queue" % (form.id))

        # create temporary build directory
        build_dir = tempfile.mkdtemp(prefix='fatbuildr', dir=self.conf.dirs.tmp)
        CleanupRegistry.add_tmpdir(build_dir)
        logger.debug("Created tmp directory %s" % (build_dir))

        # attach the build directory to the build
        form.build_dir = build_dir

        # extract artefact tarball
        tar_path = os.path.join(self.conf.dirs.queue, form.id, 'artefact.tar.xz')
        logger.debug("Extracting tarball %s" % (tar_path))
        tar = tarfile.open(tar_path, 'r:xz')
        tar.extractall(path=build_dir)
        tar.close()

        # create build state file and write the temporary build directory
        state_path = os.path.join(self.conf.dirs.queue, form.id, 'state')
        logger.debug("Creating state file %s" % (state_path))
        with open(state_path, 'w+') as fh:
            fh.write(build_dir)

    def archive(self, form):

        dest = os.path.join(self.conf.dirs.archives, form.id)
        logger.info("Moving build directory %s to archives directory %s" % (form.build_dir, dest))
        shutil.move(form.build_dir, dest)
        CleanupRegistry.del_tmpdir(form.build_dir)

        build_dir = os.path.join(self.conf.dirs.queue, form.id)
        yml_path = os.path.join(build_dir, 'build.yml')
        logger.info("Moving YAML build description file %s to archives directory %s" % (yml_path, dest))
        shutil.move(yml_path, dest)

        logger.info("Removing build %s from queue" % (form.id))
        shutil.rmtree(build_dir)

    @staticmethod
    def _load_from_yaml_path(build_id, state, build_dir, path):
        with open(path, 'r') as fh:
            return BuildForm.fromyaml(build_id, state, build_dir, fh)

    def _load_build_state(self, _dir, build_id):
        """Return (state, build_dir) for build_id in _dir."""

        # builds in archives are finished
        if _dir == self.conf.dirs.archives:
            build_dir = os.path.join(self.conf.dirs.archives, build_id)
            return ("finished", build_dir)

        # check presence of state file and set build_dir if present
        state = None
        build_dir = None
        state_path = os.path.join(_dir, build_id, 'state')
        if os.path.exists(state_path):
            state = "running"
            with open(state_path) as fh:
                build_dir = fh.read()
        else:
            state = "pending"
            build_dir = None

        return (state, build_dir)

    def _load_forms(self):
        _forms = []
        for build_id in os.listdir(self.conf.dirs.queue):
            (state, build_dir) = self._load_build_state(self.conf.dirs.queue, build_id)
            yml_path = os.path.join(self.conf.dirs.queue, build_id, 'build.yml')
            _forms.append(self._load_from_yaml_path(build_id, state, build_dir, yml_path))
         # Returns build forms sorted by submission timestamps
        _forms.sort(key=lambda build: build.submission)
        return _forms

    def dump(self):
        """Print all builds forms in the queue."""
        for form in self._load_forms():
            form.dump()

    def load(self):
        return self._load_forms()

    def get(self, build_id):
        """Return the BuildForm with the build_id in argument, looking both in
           the queue and in the archives."""

        state = None
        build_dir = None
        if build_id in os.listdir(self.conf.dirs.queue):
            logger.debug("Found build %s in queue" % (build_id))
            (state, build_dir) = self._load_build_state(self.conf.dirs.queue, build_id)
            yml_path = os.path.join(self.conf.dirs.queue, build_id, 'build.yml')
        elif build_id in os.listdir(self.conf.dirs.archives):
            logger.debug("Found build %s in archives" % (build_id))
            (state, build_dir) = self._load_build_state(self.conf.dirs.archives, build_id)
            yml_path = os.path.join(self.conf.dirs.archives, build_id, 'build.yml')
        else:
            raise RuntimeError("Unable to find build %s" % (build_id))

        return QueueManager._load_from_yaml_path(build_id, state, build_dir, yml_path)
