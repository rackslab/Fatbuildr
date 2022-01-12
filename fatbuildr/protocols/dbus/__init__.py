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
from dasbus.structure import DBusData
from dasbus.typing import Str, Int


# Define the error mapper.
ERROR_MAPPER = ErrorMapper()

# Define the message bus.
BUS = SystemMessageBus(
    error_mapper=ERROR_MAPPER
)

# Define namespaces.
REGISTER_NAMESPACE = ("org", "rackslab", "Fatbuildr")

# Define services and objects.
REGISTER = DBusServiceIdentifier(
    namespace=REGISTER_NAMESPACE,
    message_bus=BUS
)

# The decorator for DBus errors.
dbus_error = get_error_decorator(ERROR_MAPPER)


# Define errors.
@dbus_error("InvalidUserError", namespace=REGISTER_NAMESPACE)
class InvalidUser(DBusError):
    """The user is invalid."""
    pass

# Define structures.
class DbusBuild(DBusData):
    """The user data."""

    def __init__(self, id, path):
        self._id = id
        self._path = path

    @property
    def id(self) -> Str:
        """Id of the build."""
        return self._id

    @id.setter
    def id(self, value: Str):
        self._id = value

    @property
    def path(self) -> Str:
        """Path to the build."""
        return self._path

    @path.setter
    def path(self, value: Str):
        self._path = value
