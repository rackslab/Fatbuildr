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

class BuildJob(object):

    def __init__(self, source, user, email, instance, distribution, environment, fmt, artefact, submission, message, id=str(uuid.uuid4())):
        self.id = id
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
        print("Job %s" % (self.id))
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
    def fromyaml(cls, id, stream):
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
                   id=id)


class JobManager(object):
    """Manage artefact build jobs."""

    def __init__(self, conf):
        self.conf = conf

    def submit(self):
        # create tmp job directory
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

        # create yaml job description
        job = BuildJob(pipelines.name,
                       self.conf.run.user_name,
                       self.conf.run.user_email,
                       self.conf.run.instance,
                       self.conf.run.distribution,
                       pipelines.dist_env(self.conf.run.distribution),
                       pipelines.dist_format(self.conf.run.distribution),
                       self.conf.run.artefact,
                       datetime.now(),
                       msg)

        yml_path = os.path.join(tmpdir, 'job.yml')
        logger.debug("Creating YAML job description file %s" % (yml_path))
        with open(yml_path, 'w+') as fh:
            yaml.dump(job.todict(), fh)

        # move tmp job directory in queue
        dest = os.path.join(self.conf.dirs.queue, job.id)
        logger.debug("Moving tmp directory %s to %s" % (tmpdir, dest))
        shutil.move(tmpdir, dest)
        CleanupRegistry.del_tmpdir(tmpdir)
        logger.info("Build job %s submited" % (job.id))

    def pick(self, job):

        logger.info("Picking up job %s from queue" % (job.id))
        # create tmp job directory
        tmpdir = tempfile.mkdtemp(prefix='fatbuildr', dir=self.conf.dirs.tmp)
        CleanupRegistry.add_tmpdir(tmpdir)
        logger.debug("Created tmp directory %s" % (tmpdir))

        # extract artefact tarball
        tar_path = os.path.join(self.conf.dirs.queue, job.id, 'artefact.tar.xz')
        logger.debug("Extracting tarball %s" % (tar_path))
        tar = tarfile.open(tar_path, 'r:xz')
        tar.extractall(path=tmpdir)
        tar.close()

        # create job state file and write tmpdir
        state_path = os.path.join(self.conf.dirs.queue, job.id, 'state')
        logger.debug("Creating state file %s" % (state_path))
        with open(state_path, 'w+') as fh:
            fh.write(tmpdir)

        return tmpdir

    def _load_jobs(self):
        _jobs = []
        jobs_dirs = os.listdir(self.conf.dirs.queue)
        for _dir in jobs_dirs:
            yml_path = os.path.join(self.conf.dirs.queue, _dir, 'job.yml')
            with open(yml_path, 'r') as fh:
                _jobs.append(BuildJob.fromyaml(_dir, fh))
         # Returns jobs sorted by submission timestamps
        _jobs.sort(key=lambda job: job.submission)
        return _jobs

    def dump(self):
        """Print about jobs in the queue."""
        for job in self._load_jobs():
            job.dump()

    def load(self):
        return self._load_jobs()

    def remove(self, job):
        logger.info("Removing job %s from queue" % (job.id))
        job_dir = os.path.join(self.conf.dirs.queue, job.id)
        shutil.rmtree(job_dir)
