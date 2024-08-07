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

import uuid
import threading
import pickle
import shutil
import subprocess
from collections import deque

from ..errors import FatbuildrTaskExecutionError
from ..log import logr
from ..protocols.exports import ProtocolRegistry

logger = logr(__name__)


class InterruptableSemaphore(threading.Semaphore):
    """Override threading.Semaphore acquire to make acquire interruptable
    before the timeout by notifying the internal threading.Condition."""

    def acquire(self, timeout=None):
        rc = False
        with self._cond:
            if self._value == 0:
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
        self.workspaces = self.conf.tasks.workspaces.joinpath(instance.id)
        if not self.workspaces.exists():
            logger.debug(
                "Creating instance %s workspaces directory %s",
                instance.id,
                self.workspaces,
            )
            self.workspaces.mkdir()
            self.workspaces.chmod(0o755)  # be umask agnostic
        self.queue = QueueManager()
        self.queue_state_path = self.workspaces.joinpath('tasks.queue')
        self.running = None
        self.registry = ProtocolRegistry()

    @property
    def empty(self):
        self.queue.empty()

    @property
    def fullqueue(self):
        """Returns the list of running and pending tasks."""
        queue = self.queue.dump()
        running = self.running
        # The task could have been selected for running right after the queue is
        # dumped. To avoid duplication of tasks in the resulting list, the
        # presence of the running task is checked in queue dump before
        # insertion.
        if running is not None and running.id not in [
            task.id for task in queue
        ]:
            queue.insert(0, running)
        return queue

    def save(self):
        tasks = self.queue.dump()
        if not len(tasks):
            if self.queue_state_path.exists():
                self.queue_state_path.unlink()
            return
        logger.info("Saving queue state on disk")
        with open(self.queue_state_path, 'wb+') as fh:
            pickle.dump([task.id for task in tasks], fh)

    def restore(self):
        if not self.queue_state_path.exists():
            return []
        with open(self.queue_state_path, 'rb') as fh:
            try:
                return pickle.load(fh)
            except EOFError:
                return []

    def interrupt(self):
        """Interrupt thread blocked in self.pick()->self.queue.get(timeout)."""
        self.queue.interrupt_get()

    def submit(self, name, user, *args):

        task_id = str(uuid.uuid4())  # generate task ID
        place = self.workspaces.joinpath(task_id)
        try:
            task = self.registry.task_loader(name)(
                task_id, user, place, self.instance, *args
            )
        except RuntimeError as err:
            logger.error(
                "Unable to load %s task request %s: %s", name, task_id, err
            )
            return None
        self.queue.put(task)
        self.save()
        logger.info("%s task %s submitted in queue", name.capitalize(), task.id)
        return task_id

    def pick(self, timeout):

        logger.debug("Trying to get task for up to %d seconds", int(timeout))
        task = self.queue.get(timeout)
        if not task:
            return None

        logger.info("Picking up task %s from queue", task.id)

        self.running = task
        self.queue.release()
        logger.info("Task %s removed from queue", task.id)
        return task

    def _run_hook(self, task, stage: str) -> None:
        """Execute hook program if defined with some environment variable to
        provide some context."""
        if self.conf.tasks.hook is None:
            return
        target = self.conf.tasks.hook.resolve()
        if not target.is_file():
            logger.error("Tasks hook %s is not a valid file", target)
            return
        # Execute hook with environment variables
        try:
            subprocess.run(
                [target.absolute()],
                env={
                    "FATBUILDR_INSTANCE_ID": self.instance.id,
                    "FATBUILDR_INSTANCE_NAME": self.instance.name,
                    "FATBUILDR_TASK_ID": task.id,
                    "FATBUILDR_TASK_NAME": task.TASK_NAME,
                    "FATBUILDR_TASK_METADATA": task.b64_metadata(),
                    "FATBUILDR_TASK_STAGE": stage,
                    "FATBUILDR_TASK_RESULT": task.result,
                },
                timeout=5,
            )
        except PermissionError as err:
            logger.error("Error while running task hook: %s", str(err))
        except subprocess.TimeoutExpired:
            logger.error("Task hook timeout")

    def run(self, task):
        logger.info("Running task %s", task.id)
        task.prerun()
        # execute hook
        self._run_hook(task, "start")
        try:
            task.run()
        except (FatbuildrTaskExecutionError, RuntimeError) as err:
            logger.error("error while running task %s: %s", task.id, err)
            logger.info("Task failed")
            task.result = "failed"
        else:
            logger.info("Task succeeded")
            task.result = "success"
        task.postrun()
        # execute hook
        self._run_hook(task, "end")
        task.terminate()
        self.running = None
        self.save()

    def clear(self):
        """Remove the workspaces directories of all tasks found in queue state
        file. This method is called by fatbuildrd after a fresh start, before
        launching network servers, to cleanup optional orphaned tasks
        directories let by previous failed runs."""
        for task_id in self.restore():
            workspace = self.workspaces.joinpath(task_id)
            logger.warning(
                "Clearing orphaned task workspace directory %s", workspace
            )
            try:
                shutil.rmtree(workspace)
            except FileNotFoundError:
                logger.info(
                    "Orphaned workspace directory %s, ignoring", workspace
                )
                pass
        self.save()
