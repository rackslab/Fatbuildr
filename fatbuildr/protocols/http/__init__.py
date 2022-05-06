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


from ..wire import (
    WireData,
    WireInstance,
    WireRunnableTask,
    WireArtifact,
    WireChangelogEntry,
    WireTaskIO,
)
from ..exports import ProtocolRegistry


def type_fields(type):
    """Returns the set of ExportableFields for the given
    JsonData type."""
    for native_type, dbus_type, json_type in TYPES_MAP:
        if json_type is type:
            return ProtocolRegistry().type_fields(native_type)
    raise RuntimeError(f"Unable to find fields for json type {type}")


def json_type(_dbus_type):
    """Returns the JsonData type for the given Dbus type."""
    for native_type, dbus_type, json_type in TYPES_MAP:
        if dbus_type == _dbus_type:
            return json_type
    raise RuntimeError(f"Unable to find json type for dbus type {_dbus_type}")


class JsonData:
    @classmethod
    def load_from_json(cls, fields, json):
        obj = cls()
        for field in fields:
            setattr(obj, field.name, field.native(value=json[field.name]))
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
                value = json_type(type(wire_value).__name__).export(wire_value)
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


class JsonArtifact(JsonNativeData, WireArtifact):
    pass


class JsonChangelogEntry(JsonNativeData, WireChangelogEntry):
    pass


class JsonTaskIO(JsonNativeData, WireTaskIO):
    pass


# Map fatbuildr native exportable types and dbus types with corresponding json types

TYPES_MAP = {
    ('RunningInstance', 'DbusInstance', JsonInstance),
    ('RegistryArtifact', 'DbusArtifact', JsonArtifact),
    ('ChangelogEntry', 'DbusChangelogEntry', JsonChangelogEntry),
    ('TaskIO', 'DbusTaskIO', JsonTaskIO),
}
