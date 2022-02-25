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
    def export(self):
        """Export object as a dict of fields."""
        return {
            field.name: field.export(self)
            for field in self.EXFIELDS
        }


class ExportableField:
    def __init__(self, name, native_type=str):
        self.name = name
        self.native_type = native_type
        if native_type is datetime:
            self.wire_type = int
        elif native_type is Path:
            self.wire_type = str
        else:
            self.wire_type = native_type

    def export(self, obj):
        """Convert field to wire type."""
        value = getattr(obj, self.name)
        if value is None:
            return value
        assert isinstance(value, get_class_type(self.native_type))
        if self.native_type is datetime:
            return int(value.timestamp())
        elif self.native_type is Path:
            return str(value)
        elif issubclass(self.native_type, ExportableType):
            return value.export()
        return value

    def native(self, obj=None, value=None):
        """Convert field to Fatbuildr native type. Either obj or value must
        be given in args, but not both."""
        assert (obj is None and value is not None) or (
            obj is not None and value is None
        )
        if obj:
            value = getattr(obj, self.name)
        assert isinstance(value, get_class_type(self.wire_type))
        if self.native_type is datetime:
            return datetime.fromtimestamp(value)
        elif self.native_type is Path:
            return Path(value)
        elif issubclass(self.native_type, ExportableType):
            return self.native_type(**value)
        return value


class ExportableTaskField(ExportableField):
    def __init__(self, name, native_type=str, archived=True):
        super().__init__(name, native_type)
        self.archived = archived


class ProtocolRegistry(metaclass=Singleton):
    def __init__(self):
        self._tasks = {}
        self._types = {}

    def register_task(self, task):
        self._tasks[task.TASK_NAME] = task.BASEFIELDS | task.EXFIELDS

    def task_fields(self, task):
        return self._tasks[task]

    def register_type(self, type):
        self._types[type.__name__] = {'loader': type, 'fields': type.EXFIELDS}

    def type_fields(self, type):
        return self._types[type]['fields']

    def type_loader(self, type):
        return self._types[type]['loader']
