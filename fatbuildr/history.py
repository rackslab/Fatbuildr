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

import re
import os
import shutil
from datetime import datetime
from pathlib import Path

import yaml

from .tasks import RunnableTask
from .protocols.exports import ProtocolRegistry
from .errors import FatbuildrSystemConfigurationError
from .log import logr

logger = logr(__name__)


class TaskForm:

    YML_FILE = 'task.yml'

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def todict(self):
        result = {}
        for attribute in vars(self):
            # check attribute is not callable?
            result[attribute] = getattr(self, attribute)
        return result

    def save(self, dest):
        path = Path(dest, TaskForm.YML_FILE)
        logger.debug("Saving task form YAML file %s", path)
        with open(path, 'w+') as fh:
            yaml.dump(self.todict(), fh)

    @classmethod
    def fromArchive(cls, path):
        logger.debug("Loading task form in directory %s", path)
        with open(path.joinpath(TaskForm.YML_FILE), 'r') as fh:
            description = yaml.load(fh, Loader=yaml.FullLoader)
            return cls(**description)


class ArchivedTask(RunnableTask):
    def __init__(self, task_id, place, instance, **kwargs):
        self.TASK_NAME = kwargs['name']
        super().__init__(
            task_id,
            kwargs['user'],
            place,
            instance,
            state='finished',
            submission=kwargs['submission'],
        )
        for field, value in kwargs.items():
            if not hasattr(self, field):
                setattr(self, field, value)
        self.histid = '-'.join(
            [self.TASK_NAME]
            + [
                getattr(self, field.name)
                for field in ProtocolRegistry().task_fields(self.TASK_NAME)
                if field.histid
            ]
        )


class HistoryPurgePolicy:
    """Abstract history purge policy class."""

    def __init__(self, tasks, value):
        self.tasks = tasks
        self.value = value
        self.removed_tasks = 0
        self.retrieved_size = 0

    def run(self):
        raise NotImplementedError()

    @staticmethod
    def directory_size(path):
        total = 0
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_file():
                    total += entry.stat().st_size
                elif entry.is_dir():
                    total += HistoryPurgePolicy.directory_size(entry.path)
        return total

    def remove(self, task):
        self.removed_tasks += 1
        self.retrieved_size += HistoryPurgePolicy.directory_size(task.place)
        shutil.rmtree(task.place)

    def report(self):
        logger.info(
            "Purge policy has removed %d task(s) workspace(s) and retrieved "
            "%.3fMB",
            self.removed_tasks,
            self.retrieved_size / 1024 ** 2,
        )


class HistoryPurgeOlder(HistoryPurgePolicy):
    """History purge policy to remove all tasks workspaces older than a
    duration."""

    def __init__(self, tasks, value):
        super().__init__(tasks, value)
        m = re.search(r'(\d+)([a-z])', value)
        if m is None:
            raise FatbuildrSystemConfigurationError(
                f"history purge older policy value '{value}' is not supported"
            )

        quantity = int(m.group(1))
        unit = m.group(2)
        if unit == 'h':
            multiplier = 3600
        elif unit == 'd':
            multiplier = 86400
        elif unit == 'm':
            multiplier = 86400 * 30
        elif unit == 'y':
            multiplier = 86400 * 365
        else:
            raise FatbuildrSystemConfigurationError(
                f"history purge older policy unit '{unit}' is not supported"
            )
        self.value = datetime.fromtimestamp(
            datetime.now().timestamp() - quantity * multiplier
        )

    def run(self):
        for task in self.tasks:
            if task.submission < self.value:
                logger.info(
                    "removing task %s workspace with submission %s before %s",
                    task.id,
                    task.submission.isoformat(),
                    self.value.isoformat(),
                )
                self.remove(task)
            else:
                logger.info(
                    "keeping task %s workspace with submission %s after %s",
                    task.id,
                    task.submission.isoformat(),
                    self.value.isoformat(),
                )


class HistoryPurgeLast(HistoryPurgePolicy):
    """History purge policy to remove all tasks workspaces except the last n."""

    def __init__(self, tasks, value):
        super().__init__(tasks, value)
        try:
            self.value = int(value)
        except ValueError:
            raise FatbuildrSystemConfigurationError(
                f"history purge last policy value '{value}' is not supported"
            )

    def run(self):
        kept = 0
        for task in self.tasks:
            if kept < self.value:
                logger.info(
                    "keeping task %s number %d among last %d tasks",
                    task.id,
                    kept + 1,
                    self.value,
                )
                kept += 1
                continue
            logger.info(
                "removing task %s workspace out of last %d tasks",
                task.id,
                self.value,
            )
            self.remove(task)


class HistoryPurgeEach(HistoryPurgePolicy):
    """History purge policy to keep only the last n workspaces of each tasks."""

    def __init__(self, tasks, value):
        super().__init__(tasks, value)
        try:
            self.value = int(value)
        except ValueError:
            raise FatbuildrSystemConfigurationError(
                f"history purge each policy value '{value}' is not supported"
            )

    def run(self):
        tasks = dict()
        for task in self.tasks:
            if task.histid not in tasks:
                tasks[task.histid] = 1
            else:
                tasks[task.histid] += 1
            if tasks[task.histid] > self.value:
                logger.info(
                    "removing task %s (%s) workspace above each limit %d",
                    task.id,
                    task.histid,
                    self.value,
                )
                self.remove(task)
            else:
                logger.info(
                    "keeping task %s (%s) workspace number %d below each limit "
                    "%d",
                    task.id,
                    task.histid,
                    tasks[task.histid],
                    self.value,
                )


class HistoryPurgeSize(HistoryPurgePolicy):
    """History purge policy to remove older tasks until the whole history is a
    size limit."""

    def __init__(self, tasks, value):
        super().__init__(tasks, value)
        m = re.search(r"(\d+(.\d+)?)(TB|Tb|GB|Gb|MB|Mb)", value)
        if m is None:
            raise FatbuildrSystemConfigurationError(
                f"history purge size policy value '{value}' is not supported"
            )

        quantity = float(m.group(1))
        unit = m.group(3)
        if unit == 'Mb':
            multiplier = (10 ** 6) / 8
        elif unit == 'MB':
            multiplier = 1024 ** 2
        elif unit == 'Gb':
            multiplier = (10 ** 9) / 8
        elif unit == 'GB':
            multiplier = 1024 ** 3
        elif unit == 'Tb':
            multiplier = (10 ** 12) / 8
        elif unit == 'TB':
            multiplier = 1024 ** 4
        else:
            raise FatbuildrSystemConfigurationError(
                f"history purge size policy unit '{unit}' is not supported"
            )
        self.value = int(quantity * multiplier)

    def run(self):
        measured_size = 0
        for task in self.tasks:
            if measured_size < self.value:
                measured_size += HistoryPurgePolicy.directory_size(task.place)
            if measured_size >= self.value:
                logger.info(
                    "removing task %s workspace above size limit %d bytes",
                    task.id,
                    self.value,
                )
                self.remove(task)
            else:
                logger.info(
                    "keeping task %s workspace with measured size %s bytes "
                    "below size limit %d bytes",
                    task.id,
                    measured_size,
                    self.value,
                )


class HistoryPurgeFactory:

    _policies = {
        'older': HistoryPurgeOlder,
        'last': HistoryPurgeLast,
        'each': HistoryPurgeEach,
        'size': HistoryPurgeSize,
    }

    @staticmethod
    def get(mgr, policy, value):
        """Returns the HistoryPurge corresponding to the given policy."""
        if policy not in HistoryPurgeFactory._policies:
            raise FatbuildrSystemConfigurationError(
                f"policy {policy} is not supported"
            )
        return HistoryPurgeFactory._policies[policy](mgr, value)


class HistoryManager:
    def __init__(self, conf, instance):
        self.conf = conf
        self.instance = instance
        self.path = conf.tasks.workspaces.joinpath(instance.id)

    def save_task(self, task):
        fields = {
            field.name: field.export(task)
            for field in ProtocolRegistry().task_fields(task.name)
            if field.archived
        }

        form = TaskForm(**fields)
        form.save(task.place)

    def dump(self, limit, remove_malformed=False):
        """Returns up to limit last tasks found in archives directory."""
        tasks = []

        queued_tasks = [task.id for task in self.instance.tasks_mgr.fullqueue]

        # Return empty list if directory does not exist
        if not self.path.exists():
            return tasks

        for task_dir in self.path.iterdir():
            if not task_dir.is_dir():
                logger.debug("skipping non directory %s", task_dir)
                continue
            if task_dir.name in queued_tasks:
                logger.debug("skipping queued task workspace %s", task_dir)
                continue
            try:
                form = TaskForm.fromArchive(task_dir)

                fields = {
                    field.name: field.native(form)
                    for field in ProtocolRegistry().task_fields(form.name)
                    if field.archived
                }

                task = ArchivedTask(
                    task_dir.stem, task_dir, self.instance, **fields
                )

                tasks.append(task)

            except FileNotFoundError as err:
                logger.error(
                    "Unable to load malformed task directory %s: %s",
                    task_dir,
                    err,
                )
                if remove_malformed:
                    logger.info(
                        "Removing malformed task directory %s", task_dir
                    )
                    shutil.rmtree(task_dir)
            except (AttributeError, KeyError) as err:
                logger.error(
                    "Unable to load unsupported task %s: %s",
                    task_dir,
                    err,
                )
        # sort tasks by submission date, from the most recent to the oldest
        tasks.sort(key=lambda x: x.submission, reverse=True)
        if limit:
            return tasks[:limit]
        else:
            return tasks

    def purge(self):
        """Purge tasks history with the policy and its limit value defined in
        configuration."""
        policy = HistoryPurgeFactory.get(
            self.dump(limit=0, remove_malformed=True),
            self.conf.tasks.purge_policy,
            self.conf.tasks.purge_value,
        )
        policy.run()
        policy.report()
