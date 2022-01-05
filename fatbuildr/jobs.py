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
        description = {
            'instance': self.conf.app.instance,
            'distribution': self.conf.app.distribution,
            'environment': pipelines.dist_env(self.conf.app.distribution),
            'format': pipelines.dist_format(self.conf.app.distribution),
            'artefact': self.conf.app.artefact,
            'submission': int(datetime.now().timestamp()),
        }
        yml_path = os.path.join(tmpdir, 'job.yml')
        logger.debug("Creating YAML job description file %s" % (yml_path))
        with open(yml_path, 'w+') as fh:
            yaml.dump(description, fh)

        # generate random build id
        build_id = str(uuid.uuid4())

        # move tmp job directory in queue
        dest = os.path.join(self.conf.dirs.queue, build_id)
        logger.debug("Moving tmp directory %s to %s" % (tmpdir, dest))
        shutil.move(tmpdir, dest)
        CleanupRegistry.del_tmpdir(tmpdir)
        logger.info("Build job %s submited" % (build_id))

    def list(self):
        """Print about jobs in the queue."""
        jobs_dirs = os.listdir(self.conf.dirs.queue)
        for _dir in jobs_dirs:
            yml_path = os.path.join(self.conf.dirs.queue, _dir, 'job.yml')
            with open(yml_path, 'r') as fh:
                description = yaml.load(fh, Loader=yaml.FullLoader)
            print("Job %s" % (_dir))
            print("  instance: %s" % (description['instance']))
            print("  distribution: %s" % (description['distribution']))
            print("  environment: %s" % (description['environment']))
            print("  format: %s" % (description['format']))
            print("  artefact: %s" % (description['artefact']))
            print("  submission: %s" % (datetime.fromtimestamp(description['submission']).isoformat(sep=' ',timespec='seconds')))
