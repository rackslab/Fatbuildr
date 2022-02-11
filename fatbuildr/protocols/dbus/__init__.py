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
from dasbus.typing import Str, Int, List

from ..wire import WireBuild, WireArtefact, WireChangelogEntry

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
        self._derivatives = None
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

    # derivatives
    @property
    def derivatives(self) -> List[Str]:
        return self._derivatives

    @derivatives.setter
    def derivatives(self, value: List[Str]):
        self._derivatives = value

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


class DbusSubmittedBuild(DbusBuild):
    pass


class DbusStartedBuild(DbusBuild):
    def __init__(self):
        self._logfile = None

    # logfile
    @property
    def logfile(self) -> Str:
        return self._logfile

    @logfile.setter
    def logfile(self, value: Str):
        self._logfile = value


class DbusRunningBuild(DbusStartedBuild):
    pass


class DbusArchivedBuild(DbusStartedBuild):
    pass


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
