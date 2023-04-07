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

import inspect
from typing import List

from ..wire import (
    WireData,
    WireInstance,
    WireSourceArchive,
    WireRunnableTask,
    WireArtifact,
    WireChangelogEntry,
    WireTaskIO,
    WireTaskJournal,
)
from ..exports import ProtocolRegistry, ExportableType


def type_fields(type):
    """Returns the set of ExportableFields for the given
    JsonData type."""
    for native_type, dbus_type, json_type in TYPES_MAP:
        if json_type is type:
            return ProtocolRegistry().type_fields(native_type)
    raise RuntimeError(f"Unable to find fields for json type {type}")


def dbus_json_type(_dbus_type):
    """Returns the JsonData type for the given DBus type."""
    for native_type, dbus_type, json_type in TYPES_MAP:
        if dbus_type == _dbus_type:
            return json_type
    raise RuntimeError(f"Unable to find json type for dbus type {_dbus_type}")


def native_json_type(_native_type):
    """Returns the JsonData type for the given native type."""
    for native_type, _, json_type in TYPES_MAP:
        if native_type == _native_type:
            return json_type
    raise RuntimeError(f"Unable to find json type for dbus type {_dbus_type}")


class JsonData:
    @classmethod
    def load_from_json(cls, fields, json):
        obj = cls()
        for field in fields:
            wire_value = json[field.name]
            if inspect.isclass(field.wire_type) and issubclass(
                field.wire_type, ExportableType
            ):
                # If the field has an exportable type, convert the JSON to
                # the corresponding JsonNativeData type.
                native_value = native_json_type(
                    field.native_type.__name__
                ).load_from_json(wire_value)
            else:
                native_value = field.native(value=wire_value)
            setattr(obj, field.name, native_value)
        return obj

    @classmethod
    def export(cls, fields, obj):

        # If object is None, export it as None value
        if obj is None:
            return None

        result = {}
        for field in fields:
            wire_value = getattr(obj, field.name)
            # if field value is a nested WireData object, call recursive
            # JsonData.export() on this value.
            if issubclass(type(wire_value), WireData):
                value = dbus_json_type(type(wire_value).__name__).export(
                    wire_value
                )
            # If the field wire type is a List[ExportableType], build a list of
            # native JSON objects corresponding to the FatbuildrDBusData class
            # of the value in the list.
            elif isinstance(
                field.wire_type, type(List[ExportableType])
            ) and issubclass(field.wire_type.__args__[0], ExportableType):
                value = [
                    dbus_json_type(type(value).__name__).export(value)
                    for value in wire_value
                ]
            else:
                value = field.export(obj)
            result[field.name] = value
        return result


class JsonRunnableTask(JsonData, WireRunnableTask):
    @classmethod
    def load_from_json(cls, json):
        fields = ProtocolRegistry().task_fields(json['name'])
        return super().load_from_json(fields, json)

    @classmethod
    def export(cls, obj):
        fields = ProtocolRegistry().task_fields(obj.name)
        return super().export(fields, obj)


class JsonNativeData(JsonData):
    @classmethod
    def load_from_json(cls, json):
        fields = type_fields(cls)
        return super().load_from_json(fields, json)

    @classmethod
    def export(cls, obj):
        fields = type_fields(cls)
        return super().export(fields, obj)


class JsonInstance(JsonNativeData, WireInstance):
    pass


class JsonSourceArchive(JsonNativeData, WireSourceArchive):
    pass


class JsonArtifact(JsonNativeData, WireArtifact):
    pass


class JsonChangelogEntry(JsonNativeData, WireChangelogEntry):
    pass


class JsonTaskIO(JsonNativeData, WireTaskIO):
    pass


class JsonTaskJournal(JsonNativeData, WireTaskJournal):
    pass


# Map fatbuildr native exportable types and dbus types with corresponding json types

TYPES_MAP = {
    ('RunningInstance', 'DBusInstance', JsonInstance),
    ('ArtifactSourceArchive', 'DBusSourceArchive', JsonSourceArchive),
    ('RegistryArtifact', 'DBusArtifact', JsonArtifact),
    ('ChangelogEntry', 'DBusChangelogEntry', JsonChangelogEntry),
    ('TaskIO', 'DBusTaskIO', JsonTaskIO),
    ('TaskJournal', 'DBusTaskJournal', JsonTaskJournal),
}
