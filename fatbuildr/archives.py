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

import shutil
from pathlib import Path
from datetime import datetime

import yaml

from .tasks import RunnableTask
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


class ExportableField:
    def __init__(self, name, native_type=str, archived=True):
        self.name = name
        self.native_type = native_type
        if native_type is datetime:
            self.wire_type = int
        elif native_type is Path:
            self.wire_type = str
        else:
            self.wire_type = native_type
        self.archived = archived

    def export(self, value):
        if value is None:
            return value
        assert isinstance(value, self.native_type)
        if self.native_type is datetime:
            return int(value.timestamp())
        elif self.native_type is Path:
            return str(value)
        return value

    def native(self, value):
        assert isinstance(value, self.wire_type)
        if self.native_type is datetime:
            return datetime.fromtimestamp(value)
        elif self.native_type is Path:
            return Path(value)
        return value


class ArchivedTask(RunnableTask):
    def __init__(self, task_id, place, instance, **kwargs):
        super().__init__(
            kwargs['name'],
            task_id,
            place,
            instance,
            state='finished',
            submission=kwargs['submission'],
        )
        for field, value in kwargs.items():
            if not hasattr(self, field):
                setattr(self, field, value)


class ArchivesManager:

    BASEFIELDS = {
        ExportableField('id', archived=False),
        ExportableField('name'),
        ExportableField('submission', datetime),
        ExportableField('place', Path, archived=False),
        ExportableField('state', archived=False),
        ExportableField('logfile', Path, archived=False),
    }

    ARCHIVE_TYPES = {
        'artefact build': {
            ExportableField('format'),
            ExportableField('distribution'),
            ExportableField('derivative'),
            ExportableField('artefact'),
            ExportableField('user'),
            ExportableField('email'),
            ExportableField('message'),
        },
        'artefact deletion': {
            ExportableField('format'),
            ExportableField('distribution'),
            ExportableField('derivative'),
            ExportableField('artefact'),
        },
    }

    def __init__(self, conf, instance):
        self.instance = instance
        self.path = Path(conf.dirs.archives, instance.id)

    def save_task(self, task):
        if not self.path.exists:
            logger.debug("Creating instance archives directory %s", self.path)
            self.path.mkdir()
            self.path.chmod(0o755)  # be umask agnostic

        dest = self.path.joinpath(task.id)
        logger.info(
            "Moving task directory %s to archives directory %s",
            task.place,
            dest,
        )
        shutil.move(task.place, dest)

        fields = {}

        for field in self.BASEFIELDS | self.ARCHIVE_TYPES[task.name]:
            if not field.archived:
                continue
            fields[field.name] = field.export(getattr(task, field.name))

        form = TaskForm(**fields)
        form.save(dest)

    def dump(self):
        """Returns all tasks found in archives directory."""
        _archives = []

        for task_dir in self.path.iterdir():
            try:
                form = TaskForm.fromArchive(task_dir)

                fields = {}

                for field in self.BASEFIELDS | self.ARCHIVE_TYPES[form.name]:
                    if not field.archived:
                        continue
                    fields[field.name] = field.native(getattr(form, field.name))

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
        return _archives
