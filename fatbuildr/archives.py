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

from pathlib import Path

import yaml

from .tasks import RunnableTask
from .protocols.exports import ProtocolRegistry
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


class ArchivesManager:
    def __init__(self, conf, instance):
        self.instance = instance
        self.path = conf.dirs.workspaces.joinpath(instance.id)

    def save_task(self, task):
        fields = {
            field.name: field.export(task)
            for field in ProtocolRegistry().task_fields(task.name)
            if field.archived
        }

        form = TaskForm(**fields)
        form.save(task.place)

    def dump(self, limit):
        """Returns up to limit last tasks found in archives directory."""
        _archives = []

        # Return empty list if directory does not exist
        if not self.path.exists():
            return _archives

        for task_dir in self.path.iterdir():
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

                _archives.append(task)

            except FileNotFoundError as err:
                logger.error(
                    "Unable to load malformed build archive %s: %s",
                    task_dir,
                    err,
                )
            except (AttributeError, KeyError) as err:
                logger.error(
                    "Unable to load unsupported task %s: %s",
                    task_dir,
                    err,
                )
        # sort archives by submission date, from the most recent to the oldest
        _archives.sort(key=lambda x: x.submission, reverse=True)
        if limit:
            return _archives[:limit]
        else:
            return _archives
