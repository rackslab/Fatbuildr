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

from dasbus.connection import SystemMessageBus
from dasbus.error import DBusError, ErrorMapper, get_error_decorator
from dasbus.identifier import DBusServiceIdentifier
from dasbus.structure import (
    DBusData,
    DBusFieldFactory,
    DBUS_FIELDS_ATTRIBUTE,
    DBusStructureError,
)
from dasbus.typing import unwrap_variant, get_variant, Structure, Str, Int, List

from ..wire import (
    WireInstance,
    WireRunnableTask,
    WireArtifact,
    WireChangelogEntry,
    WireKeyring,
    WireTaskIO,
    WireTaskJournal,
)

from ..exports import ProtocolRegistry, ExportableType

from ...log import logr

logger = logr(__name__)

# Define the error mapper.
ERROR_MAPPER = ErrorMapper()

# Define the message bus.
BUS = SystemMessageBus(error_mapper=ERROR_MAPPER)

# Define namespaces.
FATBUILDR_NAMESPACE = ("org", "rackslab", "Fatbuildr")

# Define services and objects.
FATBUILDR_SERVICE = DBusServiceIdentifier(
    namespace=FATBUILDR_NAMESPACE, message_bus=BUS
)

# The decorator for DBus errors.
dbus_error = get_error_decorator(ERROR_MAPPER)

# Define errors.
@dbus_error("ErrorNotAuthorized", namespace=FATBUILDR_NAMESPACE)
class ErrorNotAuthorized(DBusError):
    pass


@dbus_error("ErrorNoRunningTask", namespace=FATBUILDR_NAMESPACE)
class ErrorNoRunningTask(DBusError):
    pass


@dbus_error("ErrorNoKeyring", namespace=FATBUILDR_NAMESPACE)
class ErrorNoKeyring(DBusError):
    pass


@dbus_error("ErrorArtifactNotFound", namespace=FATBUILDR_NAMESPACE)
class ErrorArtifactNotFound(DBusError):
    pass


# Utilities to handle null values


def valueornull(value):
    """Returns string 'null' if value is None, returns the value unmodified
    otherwise."""
    return value or 'null'


def valueornone(value):
    """Returns None if the value is the string 'null', returns the value
    unmodified otherwise."""
    return None if value == 'null' else value


# Utilities to manipulate TYPES_MAP


def type_fields(type):
    """Returns the set of ExportableFields for the given
    FatbuildrNativeDbusData type."""
    for native_type, dbus_type in TYPES_MAP:
        if dbus_type is type:
            return ProtocolRegistry().type_fields(native_type)
    raise RuntimeError(f"Unable to find fields for type {type}")


def dbus_type(type_name):
    """Return the FatbuildrNativeDbusData type for the given ExportableType
    name."""
    for native_type, dbus_type in TYPES_MAP:
        if type_name == native_type:
            return dbus_type
    raise RuntimeError(f"Unable to find dbus type for {type_name}")


def native_type(type):
    """Returns the ExportableType name of the given FatbuildrNativeDbusData
    type."""
    for native_type, dbus_type in TYPES_MAP:
        if dbus_type is type:
            return native_type
    raise RuntimeError(f"Unable to find native type for {type}")


# Define structures.


class FatbuildrDbusData:
    @classmethod
    def from_structure(cls, fields, structure: Structure):
        """Convert a DBus structure to a data object.
        :param structure: a DBus structure
        :return: a data object
        """
        if not isinstance(structure, dict):
            raise TypeError(
                "Invalid type '{}'.".format(type(structure).__name__)
            )

        data = cls()

        for field in fields:
            wire_value = unwrap_variant(structure[field.name])
            if (field.wire_type is int and wire_value == -1) or (
                field.wire_type is str and wire_value == '∅'
            ):
                native_value = None
            elif issubclass(field.wire_type, ExportableType):
                # If the field has an exportable type, convert the structure to
                # the corresponding FatbuildrNativeDbusData type.
                native_value = dbus_type(
                    field.wire_type.__name__
                ).from_structure(wire_value)
            else:
                native_value = field.native(value=wire_value)
            setattr(data, field.name, native_value)

        return data

    @classmethod
    def to_structure(cls, fields, task) -> Structure:
        """Convert this data object to a DBus structure.
        :return: a DBus structure
        """

        structure = {}

        for field in fields:
            native_value = getattr(task, field.name)
            # Dbus does not support None/null values, then handle this case
            # with special values.
            if native_value is None:
                if field.wire_type is int:
                    wire_value = -1
                else:
                    wire_value = '∅'
            elif issubclass(field.wire_type, ExportableType):
                # If the type is directly exportable on the wire, convert it
                # to (nested) structure.
                wire_value = dbus_type(field.wire_type.__name__).to_structure(
                    native_value
                )
            else:
                wire_value = field.export(task)

            # If the type is exported, declare it as Structure type
            if issubclass(field.wire_type, ExportableType):
                wire_type = Structure
            else:
                wire_type = field.wire_type

            structure[field.name] = get_variant(wire_type, wire_value)

        return structure

    @classmethod
    def from_structure_list(cls, structures: List[Structure]):
        """Convert DBus structures to data objects.
        :param structures: a list of DBus structures
        :return: a list of data objects
        """
        if not isinstance(structures, list):
            raise TypeError(
                "Invalid type '{}'.".format(type(structures).__name__)
            )

        return list(map(cls.from_structure, structures))

    @classmethod
    def to_structure_list(cls, objects) -> List[Structure]:
        """Convert data objects to DBus structures.
        :param objects: a list of data objects
        :return: a list of DBus structures
        """
        return list(map(cls.to_structure, objects))


class DbusRunnableTask(FatbuildrDbusData, WireRunnableTask):
    @classmethod
    def from_structure(cls, structure: Structure):
        task_name = unwrap_variant(structure['name'])
        fields = ProtocolRegistry().task_fields(task_name)
        return super().from_structure(fields, structure)

    @classmethod
    def to_structure(cls, task) -> Structure:
        fields = ProtocolRegistry().task_fields(task.name)
        return super().to_structure(fields, task)


class FatbuildrNativeDbusData(FatbuildrDbusData):
    @classmethod
    def from_structure(cls, structure: Structure):
        return super().from_structure(type_fields(cls), structure)

    @classmethod
    def to_structure(cls, task) -> Structure:
        return super().to_structure(type_fields(cls), task)

    def to_native(self):
        kwargs = {
            field.name: getattr(self, field.name)
            for field in type_fields(type(self))
        }
        return ProtocolRegistry().type_loader(native_type(type(self)))(**kwargs)


class DbusInstance(FatbuildrNativeDbusData, WireInstance):
    pass


class DbusArtifact(FatbuildrNativeDbusData, WireArtifact):
    pass


class DbusChangelogEntry(FatbuildrNativeDbusData, WireChangelogEntry):
    pass


class DbusKeyring(FatbuildrNativeDbusData, WireKeyring):
    pass


class DbusKeyringSubKey(FatbuildrNativeDbusData):
    pass


class DbusTaskIO(FatbuildrNativeDbusData, WireTaskIO):
    pass


class DbusTaskJournal(FatbuildrNativeDbusData, WireTaskJournal):
    pass


# Map fatbuildr native exportable types with corresponding dbus types

TYPES_MAP = {
    ('RunningInstance', DbusInstance),
    ('RegistryArtifact', DbusArtifact),
    ('ChangelogEntry', DbusChangelogEntry),
    ('KeyringMasterKey', DbusKeyring),
    ('KeyringSubKey', DbusKeyringSubKey),
    ('TaskIO', DbusTaskIO),
    ('TaskJournal', DbusTaskJournal),
}
