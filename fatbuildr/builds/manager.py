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
import threading
from datetime import datetime
from time import monotonic as _time
from collections import deque

from ..cleanup import CleanupRegistry
from ..log import logr
from . import BuildSubmission, BuildRequest, BuildArchive
from .factory import BuildFactory

logger = logr(__name__)


class InterruptableSemaphore(threading.Semaphore):
    """Override threading.Semaphore acquire to make acquire interruptable
    before the timeout by notifying the internal threading.Condition."""
    def acquire(self, timeout=None):
        rc = False
        with self._cond:
            if self._value == 0:
                endtime = _time() + timeout
                self._cond.wait(timeout)
            else:
                self._value -= 1
                rc = True
        return rc


class QueueManager:
    def __init__(self):
        self._queue = deque()
        self._count = InterruptableSemaphore(0)
        self._state_lock = threading.Lock()

    def empty(self):
        return len(self._queue) == 0

    def dump(self):
        with self._state_lock:
            return list(self._queue)

    def put(self, submission):
        self._queue.append(submission)
        self._count.release()

    def get(self, timeout):
        if not self._count.acquire(timeout):
            return None
        self._state_lock.acquire()
        return self._queue.popleft()

    def release(self):
        self._state_lock.release()

    def interrupt_get(self):
        """Notify the semaphore condition to interrupt thread blocked in
        self.get(timeout)"""
        self._count._cond.notify()


class ServerBuildsManager:
    """Manage the various builds."""

    def __init__(self, conf, instance):
        self.conf = conf
        self.instance = instance
        self.queue = QueueManager()
        self.running = None

    @property
    def empty(self):
        return self.queue.empty()

    def clear_orphaned(self):
        """Remove all submissions in queue directory not actually in queue, and
        archive all builds in build directory not actually running."""
        for build_id in os.listdir(self.conf.dirs.queue):
            if build_id not in [build.id for build in self.queue.dump()]:
                logger.warning(
                    "Removing orphaned build submission %s" % (build_id)
                )
                shutil.rmtree(os.path.join(self.conf.dirs.queue, build_id))
        for build_id in os.listdir(self.conf.dirs.build):
            if not self.running or build_id != self.running.id:
                logger.warning("Archiving orphaned build %s" % (build_id))
                build = BuildFactory.load(
                    self.conf,
                    self.instance,
                    os.path.join(self.conf.dirs.build, build_id),
                    build_id,
                )
                self.archive(build)

    def interrupt(self):
        """Interrupt thread blocked in self.pick()->self.queue.get(timeout)."""
        self.queue.interrupt_get()

    def submit(self, input):
        """Generate the build ID and place in queue."""

        build_id = str(uuid.uuid4())  # generate build ID
        place = os.path.join(self.conf.dirs.queue, build_id)
        request = BuildRequest.load(input)
        submission = BuildSubmission.load_from_request(place, request, build_id)
        self.queue.put(submission)
        logger.info("Build %s submitted in queue" % (submission.id))
        return submission

    def pick(self, timeout):

        logger.debug(
            "Trying to get build submission for up to %d seconds", int(timeout)
        )
        submission = self.queue.get(timeout)
        if not submission:
            return None

        logger.info(
            "Picking up build submission %s from queue" % (submission.id)
        )
        # transition the request to an artefact build
        build = None
        try:
            build = BuildFactory.generate(self.conf, self.instance, submission)
            self.running = build
        except RuntimeError as err:
            logger.error(
                "unable to generate build from submission %s: %s"
                % (submission.id, err)
            )
        finally:
            self.queue.release()
            logger.info(
                "Build submission %s removed from queue" % (submission.id)
            )
            # cleanup submission directory
            self._cleanup(submission)
        return build

    def archive(self, build):

        self.running = None
        dest = os.path.join(self.conf.dirs.archives, build.id)
        logger.info(
            "Moving build directory %s to archives directory %s"
            % (build.place, dest)
        )
        shutil.move(build.place, dest)

    def _cleanup(self, submission):
        """Remove submission temporary directory."""
        logger.debug("Deleting submission directory %s" % (submission.place))
        shutil.rmtree(submission.place)

    def archives(self):
        """Returns all BuildArchive found in archives directory."""
        _archives = []
        for build_id in os.listdir(self.conf.dirs.archives):
            try:
                _archives.append(
                    BuildArchive(
                        os.path.join(self.conf.dirs.archives, build_id),
                        build_id,
                    )
                )
            except FileNotFoundError as err:
                logger.error(
                    "Unable to load malformed build archive %s: %s"
                    % (build_id, err)
                )
        return _archives


class ClientBuildsManager:
    def __init__(self, conf):
        self.conf = conf

    def request(
        self,
        basedir,
        subdir,
        instance,
        distribution,
        derivative,
        env,
        artefact,
        fmt,
        user_name,
        user_email,
        msg,
    ):
        # create tmp submission directory
        tmpdir = tempfile.mkdtemp(prefix='fatbuildr', dir=self.conf.dirs.tmp)
        logger.debug("Created request temporary directory %s" % (tmpdir))

        # create build request
        request = BuildRequest(
            tmpdir,
            user_name,
            user_email,
            instance,
            distribution,
            derivative,
            env,
            fmt,
            artefact,
            datetime.now(),
            msg,
        )

        # save the request form in tmpdir
        request.form.save(tmpdir)

        # prepare artefact tarball
        request.prepare_tarball(basedir, subdir, tmpdir)
        return request
