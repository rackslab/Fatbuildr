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
    WireArtefact,
    WireChangelogEntry,
    WireKeyring,
)

from ...archives import ArchivesManager

from ...log import logr

logger = logr(__name__)

# Define the error mapper.
ERROR_MAPPER = ErrorMapper()

# Define the message bus.
BUS = SystemMessageBus(error_mapper=ERROR_MAPPER)

# Define namespaces.
REGISTER_NAMESPACE = ("org", "rackslab", "Fatbuildr")

# Define services and objects.
REGISTER = DBusServiceIdentifier(namespace=REGISTER_NAMESPACE, message_bus=BUS)

# The decorator for DBus errors.
dbus_error = get_error_decorator(ERROR_MAPPER)

# Define errors.
@dbus_error("ErrorNoRunningTask", namespace=REGISTER_NAMESPACE)
class ErrorNoRunningTask(DBusError):
    pass


# Define structures.


class DbusInstance(DBusData, WireInstance):
    def __init__(self):
        self._id = None
        self._name = None
        self._userid = None

    # id
    @property
    def id(self) -> Str:
        return self._id

    @id.setter
    def id(self, value: Str):
        self._id = value

    # name
    @property
    def name(self) -> Str:
        return self._name

    @name.setter
    def name(self, value: Str):
        self._name = value

    # userid
    @property
    def userid(self) -> Str:
        return self._userid

    @userid.setter
    def userid(self, value: Str):
        self._userid = value


class DbusRunnableTask(WireRunnableTask):
    @classmethod
    def from_structure(cls, structure: Structure):
        """Convert a DBus structure to a data object.
        :param structure: a DBus structure
        :return: a data object
        """
        if not isinstance(structure, dict):
            raise TypeError(
                "Invalid type '{}'.".format(type(structure).__name__)
            )

        data = cls()
        task_name = unwrap_variant(structure['name'])
        fields = (
            ArchivesManager.BASEFIELDS
            | ArchivesManager.ARCHIVE_TYPES[task_name]
        )

        for field in fields:
            wire_value = unwrap_variant(structure[field.name])
            if (field.wire_type is int and wire_value == -1) or (
                field.wire_type is str and wire_value == '∅'
            ):
                native_value = None
            else:
                native_value = field.native(wire_value)
            setattr(data, field.name, native_value)

        return data

    @classmethod
    def to_structure(cls, task) -> Structure:
        """Convert this data object to a DBus structure.
        :return: a DBus structure
        """

        structure = {}
        fields = (
            ArchivesManager.BASEFIELDS
            | ArchivesManager.ARCHIVE_TYPES[task.name]
        )

        for field in fields:
            logger.debug(
                "Exporting field %s with value %s (%s) and expected native type %s",
                field.name,
                str(getattr(task, field.name)),
                str(type(getattr(task, field.name))),
                str(field.native_type),
            )

            native_value = getattr(task, field.name)
            # Dbus does not support None/null values, then handle this case
            # with special values.
            if native_value is None:
                if field.wire_type is int:
                    wire_value = -1
                else:
                    wire_value = '∅'
            else:
                wire_value = field.export(native_value)

            structure[field.name] = get_variant(field.wire_type, wire_value)

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


class DbusArtefact(DBusData, WireArtefact):
    def __init__(self):
        self._name = None
        self._architecture = None
        self._version = None

    # name
    @property
    def name(self) -> Str:
        return self._name

    @name.setter
    def name(self, value: Str):
        self._name = value

    # architecture
    @property
    def architecture(self) -> Str:
        return self._architecture

    @architecture.setter
    def architecture(self, value: Str):
        self._architecture = value

    # version
    @property
    def version(self) -> Str:
        return self._version

    @version.setter
    def version(self, value: Str):
        self._version = value


class DbusChangelogEntry(DBusData, WireChangelogEntry):
    def __init__(self):
        self._version = None
        self._author = None
        self._date = None
        self._changes = None

    # version
    @property
    def version(self) -> Str:
        return self._version

    @version.setter
    def version(self, value: Str):
        self._version = value

    # author
    @property
    def author(self) -> Str:
        return self._author

    @author.setter
    def author(self, value: Str):
        self._author = value

    # date
    @property
    def date(self) -> Int:
        return self._date

    @date.setter
    def date(self, value: Str):
        self._date = value

    # changes
    @property
    def changes(self) -> List[Str]:
        return self._changes

    @changes.setter
    def changes(self, value: Str):
        self._changes = value


class DbusKeyring(DBusData, WireKeyring):
    def __init__(self):
        self._userid = None
        self._id = None
        self._fingerprint = None
        self._algo = None
        self._expires = None
        self._creation = None
        self._last_update = None
        self._subkey_fingerprint = None
        self._subkey_algo = None
        self._subkey_expires = None
        self._subkey_creation = None

    # userid
    @property
    def userid(self) -> Str:
        return self._userid

    @userid.setter
    def userid(self, value: Str):
        self._userid = value

    # id
    @property
    def id(self) -> Str:
        return self._id

    @id.setter
    def id(self, value: Str):
        self._id = value

    # fingerprint
    @property
    def fingerprint(self) -> Str:
        return self._fingerprint

    @fingerprint.setter
    def fingerprint(self, value: Str):
        self._fingerprint = value

    # algo
    @property
    def algo(self) -> Str:
        return self._algo

    @algo.setter
    def algo(self, value: Str):
        self._algo = value

    # expires
    @property
    def expires(self) -> Str:
        return self._expires

    @expires.setter
    def expires(self, value: Str):
        self._expires = value

    # creation
    @property
    def creation(self) -> Str:
        return self._creation

    @creation.setter
    def creation(self, value: Str):
        self._creation = value

    # last_update
    @property
    def last_update(self) -> Str:
        return self._last_update

    @last_update.setter
    def last_update(self, value: Str):
        self._last_update = value

    # subkey_fingerprint
    @property
    def subkey_fingerprint(self) -> Str:
        return self._subkey_fingerprint

    @subkey_fingerprint.setter
    def subkey_fingerprint(self, value: Str):
        self._subkey_fingerprint = value

    # subkey_algo
    @property
    def subkey_algo(self) -> Str:
        return self._subkey_algo

    @subkey_algo.setter
    def subkey_algo(self, value: Str):
        self._subkey_algo = value

    # subkey_expires
    @property
    def subkey_expires(self) -> Str:
        return self._subkey_expires

    @subkey_expires.setter
    def subkey_expires(self, value: Str):
        self._subkey_expires = value

    # subkey_creation
    @property
    def subkey_creation(self) -> Str:
        return self._subkey_creation

    @subkey_creation.setter
    def subkey_creation(self, value: Str):
        self._subkey_creation = value
