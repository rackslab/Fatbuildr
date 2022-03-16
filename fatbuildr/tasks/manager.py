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

import tempfile
import uuid
import shutil
import threading
from datetime import datetime
from time import monotonic as _time
from collections import deque
from pathlib import Path

from ..log import logr
from ..protocols.exports import ProtocolRegistry

from ..builds.factory import BuildFactory
from .registry import RegistryArtefactDeletionTask
from .keyring import KeyringCreationTask, KeyringRenewalTask
from .images import (
    ImageCreationTask,
    ImageUpdateTask,
    ImageEnvironmentCreationTask,
    ImageEnvironmentUpdateTask,
)

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
        self.registry = ProtocolRegistry()
        # register all types of tasks with their exportable fields

    @property
    def empty(self):
        return self.queue.empty()

    def interrupt(self):
        """Interrupt thread blocked in self.pick()->self.queue.get(timeout)."""
        self.queue.interrupt_get()

    def submit(self, name, *args):

        task_id = str(uuid.uuid4())  # generate task ID
        place = self.conf.dirs.queue.joinpath(task_id)
        try:
            task = self.registry.task_loader(name)(
                task_id, place, self.instance, *args
            )
        except RuntimeError as err:
            logger.error(
                "Unable to load %s task request %s: %s", name, task_id, err
            )
            return None
        self.queue.put(task)
        logger.info("%s task %s submitted in queue", name.capitalize(), task.id)
        return task_id

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
        task.prerun()
        try:
            task.run()
        except RuntimeError as err:
            logger.error("error while running task %s: %s", task.id, err)
            logger.info("Task failed")
        else:
            logger.info("Task succeeded")
        task.postrun()
        self.running = None
        task.terminate()
