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
import uuid
import shutil
from datetime import datetime
import logging

from .pipelines import PipelinesDefs
from .cleanup import CleanupRegistry
from .builds import BuildRequest, BuildArchive
from .builds.factory import BuildFactory

logger = logging.getLogger(__name__)


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

        request = self._load_queue()[0]
        logger.info("Picking up build request %s from queue" % (request.id))
        return request

    def remove(self, request):
        """Remove request from queue."""
        logger.debug("Deleting request directory %s" % (request.place))
        shutil.rmtree(request.place)
        logger.info("Build build %s removed from queue" % (request.id))

    def archive(self, build):

        dest = os.path.join(self.conf.dirs.archives, build.id)
        logger.info("Moving build directory %s to archives directory %s" % (build.place, dest))
        shutil.move(build.place, dest)

    def _load_queue(self):
        _requests = []
        for build_id in os.listdir(self.conf.dirs.queue):
            request = BuildRequest.load(os.path.join(self.conf.dirs.queue, build_id), build_id)
            _requests.append(request)
         # Returns build requests sorted by submission timestamps
        _requests.sort(key=lambda build: build.submission)
        return _requests

    def _load_builds(self):
        _builds = []
        for build_id in os.listdir(self.conf.dirs.build):
            build = BuildFactory.load(self.conf, os.path.join(self.conf.dirs.build, build_id), build_id)
            _builds.append(build)
         # Returns build requests sorted by submission timestamps
        _builds.sort(key=lambda build: build.submission)
        return _builds

    def dump(self):
        """Print all builds requests in the queue."""
        for build in self._load_builds() + self._load_queue():
            build.dump()

    def get(self, build_id):
        """Return the BuildRequest, BuildFactory or the BuildArchive with the
           build_id in argument, looking both in the queue and in the
           archives."""

        if build_id in os.listdir(self.conf.dirs.queue):
            logger.debug("Found build %s in queue" % (build_id))
            return BuildRequest.load(os.path.join(self.conf.dirs.queue, build_id), build_id)
        elif build_id in os.listdir(self.conf.dirs.build):
            logger.debug("Found running build %s" % (build_id))
            return BuildFactory.load(self.conf, os.path.join(self.conf.dirs.build, build_id), build_id)
        elif build_id in os.listdir(self.conf.dirs.archives):
            logger.debug("Found build %s in archives" % (build_id))
            return BuildArchive(os.path.join(self.conf.dirs.archives, build_id), build_id)
        else:
            raise RuntimeError("Unable to find build %s" % (build_id))
