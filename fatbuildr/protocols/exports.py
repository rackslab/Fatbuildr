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

import types
from datetime import datetime
from pathlib import Path

from ..utils import Singleton


def get_class_type(typ):
    if isinstance(typ, types.GenericAlias):
        return typ.__origin__
    else:
        return typ


class ExportableType:
    pass


class ExportableTaskField:
    def __init__(self, name, native_type=str, archived=True):
        self.name = name
        self.native_type = native_type
        if native_type is datetime:
            self.wire_type = int
        elif native_type is Path:
            self.wire_type = str
        elif issubclass(native_type, ExportableType):
            self.wire_type = native_type.WIRE_TYPE
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
        elif issubclass(self.native_type, ExportableType):
            return value.export()
        return value

    def native(self, value):
        assert isinstance(value, get_class_type(self.wire_type))
        if self.native_type is datetime:
            return datetime.fromtimestamp(value)
        elif self.native_type is Path:
            return Path(value)
        elif issubclass(self.native_type, ExportableType):
            return self.native_type(**value)
        return value


class ProtocolRegistry(metaclass=Singleton):
    def __init__(self):
        self._tasks = {}

    def register_task(self, task):
        self._tasks[task.TASK_NAME] = task.BASEFIELDS | task.EXFIELDS

    def task_fields(self, task):
        return self._tasks[task]
