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
from dasbus.structure import DBusData, DBusFieldFactory, DBUS_FIELDS_ATTRIBUTE, DBusStructureError
from dasbus.typing import Str, Int

from ..wire import WireBuild

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

TYPES_MAP = {
    str: Str,
    int: Int,
}

# Define errors.
@dbus_error("ErrorNoRunningBuild", namespace=REGISTER_NAMESPACE)
class ErrorNoRunningBuild(DBusError):
    pass


# Define structures.
class DbusBuild(DBusData, WireBuild):
    """The user data."""

    def __init__(self):
        self._id = None
        self._state = None
        self._place = None
        self._source = None
        self._user = None
        self._email = None
        self._instance = None
        self._distribution = None
        self._environment = None
        self._format = None
        self._artefact = None
        self._submission = None
        self._message = None

    # id
    @property
    def id(self) -> Str:
        return self._id

    @id.setter
    def id(self, value: Str):
        self._id = value

    # state
    @property
    def state(self) -> Str:
        return self._state

    @state.setter
    def state(self, value: Str):
        self._state = value

    # place
    @property
    def place(self) -> Str:
        return self._place

    @place.setter
    def place(self, value: Str):
        self._place = value

    # source
    @property
    def source(self) -> Str:
        return self._source

    @source.setter
    def source(self, value: Str):
        self._source = value

    # user
    @property
    def user(self) -> Str:
        return self._user

    @user.setter
    def user(self, value: Str):
        self._user = value

    # email
    @property
    def email(self) -> Str:
        return self._email

    @email.setter
    def email(self, value: Str):
        self._email = value

    # instance
    @property
    def instance(self) -> Str:
        return self._instance

    @instance.setter
    def instance(self, value: Str):
        self._instance = value

    # distribution
    @property
    def distribution(self) -> Str:
        return self._distribution

    @distribution.setter
    def distribution(self, value: Str):
        self._distribution = value

    # environment
    @property
    def environment(self) -> Str:
        return self._environment

    @environment.setter
    def environment(self, value: Str):
        self._environment = value

    # format
    @property
    def format(self) -> Str:
        return self._format

    @format.setter
    def format(self, value: Str):
        self._format = value

    # artefact
    @property
    def artefact(self) -> Str:
        return self._artefact

    @artefact.setter
    def artefact(self, value: Str):
        self._artefact = value

    # submission
    @property
    def submission(self) -> Int:
        return self._submission

    @submission.setter
    def submission(self, value: Int):
        self._submission = value

    # message
    @property
    def message(self) -> Str:
        return self._message

    @message.setter
    def message(self, value: Str):
        self._message = value

    @classmethod
    def load_from_build(cls, build):
        _obj = cls()
        _obj.id = build.id
        _obj.state = build.state
        _obj.place = build.place
        _obj.source = build.source
        _obj.user = build.user
        _obj.email = build.email
        _obj.instance = build.instance
        _obj.distribution = build.distribution
        _obj.environment = build.environment
        _obj.format = build.format
        _obj.artefact = build.artefact
        _obj.submission = int(build.submission.timestamp())
        _obj.message = build.message
        return _obj
