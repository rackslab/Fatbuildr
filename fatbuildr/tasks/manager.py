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

from ..log import logr
from ..builds import BuildRequest, BuildArchive
from ..builds.factory import BuildFactory

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


class ServerTasksManager:
    """Manage the various builds."""

    def __init__(self, conf, instance):
        self.conf = conf
        self.instance = instance
        self.queue = QueueManager()
        self.running = None

    @property
    def empty(self):
        return self.queue.empty()

    def clear_orphaned_builds(self):
        """Remove all submissions in queue directory not actually in queue, and
        archive all builds in build directory not actually running."""
        for build_id in os.listdir(self.conf.dirs.queue):
            if not self.running or build_id != self.running.id:
                logger.warning("Archiving orphaned build %s", build_id)
                build_dir = os.path.join(self.conf.dirs.queue, build_id)
                build = BuildFactory.load(
                    self.conf,
                    self.instance,
                    build_dir,
                    build_id,
                )
                build.archive()


    def interrupt(self):
        """Interrupt thread blocked in self.pick()->self.queue.get(timeout)."""
        self.queue.interrupt_get()

    def submit(self, input):
        """Generate the build ID and place in queue."""

        task_id = str(uuid.uuid4())  # generate task ID
        request = BuildRequest.load(input)
        try:
            build = BuildFactory.generate(self.conf, self.instance, request, task_id)
        except RuntimeError as err:
            logger.error(
                "unable to generate build %s request %s: %s",
                task_id, err
            )
            return None
        self.queue.put(build)
        logger.info("Build %s submitted in queue" % (build.id))
        return build

    def pick(self, timeout):

        logger.debug("Trying to get task for up to %d seconds", int(timeout))
        task = self.queue.get(timeout)
        if not task:
            return None

        logger.info("Picking up task %s from queue" % (task.id))

        self.running = task
        self.queue.release()
        logger.info("Task %s removed from queue" % (task.id))
        return task

    def run(self, task):
        logger.info("Running task %s", task.id)
        task.run()
        self.running = None
        task.terminate()

    def archives(self):
        """Returns all BuildArchive found in archives directory."""
        _archives = []

        archives_dir = os.path.join(self.conf.dirs.archives, self.instance.id)
        for build_id in os.listdir(archives_dir):
            try:
                _archives.append(
                    BuildArchive(
                        os.path.join(archives_dir, build_id),
                        build_id,
                    )
                )
            except FileNotFoundError as err:
                logger.error(
                    "Unable to load malformed build archive %s: %s"
                    % (build_id, err)
                )
        return _archives
