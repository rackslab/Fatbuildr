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

    def __init__(self, instance, distribution, environment, fmt, artefact, submission, id=str(uuid.uuid4())):
        self.id = id
        self.instance = instance
        self.distribution = distribution
        self.environment = environment
        self.format = fmt
        self.artefact = artefact
        self.submission = submission

    def todict(self):
        return {
            'instance': self.instance,
            'distribution': self.distribution,
            'environment': self.environment,
            'format': self.format,
            'artefact': self.artefact,
            'submission': int(self.submission.timestamp())
        }

    def dump(self):
        print("Job %s" % (_dir))
        print("  instance: %s" % (self.instance))
        print("  distribution: %s" % (self.distribution))
        print("  environment: %s" % (self.environment))
        print("  format: %s" % (self.format))
        print("  artefact: %s" % (self.artefact))
        print("  submission: %s" % (self.submission.isoformat(sep=' ',timespec='seconds')))

    @classmethod
    def fromyaml(cls, id, stream):
        description = yaml.load(stream, Loader=yaml.FullLoader)
        return cls(description['instance'],
                   description['distribution'],
                   description['environment'],
                   description['format'],
                   description['artefact'],
                   datetime.fromtimestamp(description['submission']),
                   id=id)


class JobManager(object):
    """Manage artefact build jobs."""

    def __init__(self, conf):
        self.conf = conf

    def submit(self):
        # create tmp job directory
        tmpdir = tempfile.mkdtemp(dir=self.conf.dirs.tmp)
        CleanupRegistry.add_tmpdir(tmpdir)
        logger.debug("Created tmp directory %s" % (tmpdir))

        # load pipelines defs to get dist→format/env mapping
        pipelines = PipelinesDefs(self.conf.app.basedir)

        # create an archive of artefact subdirectory
        artefact_def_path = os.path.join(self.conf.app.basedir,
                                         self.conf.app.artefact,
                                         pipelines.dist_format(self.conf.app.distribution))
        if not os.path.exists(artefact_def_path):
            raise RuntimeError("artefact definition directory %s does not exist" % (artefact_def_path))

        tar_path = os.path.join(tmpdir, 'artefact.tar.xz')
        logger.debug("Creating archive %s with artefact definition directory %s" % (tar_path, artefact_def_path))
        tar = tarfile.open(tar_path, 'x:xz')
        tar.add(artefact_def_path, arcname='.', recursive=True)
        tar.close()

        # create yaml job description
        job = BuildJob(self.conf.app.instance,
                       self.conf.app.distribution,
                       pipelines.dist_env(self.conf.app.distribution),
                       pipelines.dist_format(self.conf.app.distribution),
                       self.conf.app.artefact,
                       datetime.now())

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
        logger.info("Removing job %s" % (job.id))
        job_dir = os.path.join(self.conf.dirs.queue, job.id)
        shutil.rmtree(job_dir)
