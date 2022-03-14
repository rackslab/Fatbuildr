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

from urllib.parse import urlparse

from .dbus.client import DbusClient
from .http.client import HttpClient

from .dbus.server import DbusServer


class ClientFactory(object):
    @staticmethod
    def get(address):
        uri = urlparse(address)
        instance = uri.path.strip('/')
        if uri.scheme == 'dbus':
            if not instance:
                raise RuntimeError("Instance must be defined in Dbus URI")
            return DbusClient(instance)
        elif uri.scheme in ['http', 'https']:
            return HttpClient(address)
        else:
            raise RuntimeError(f"unsupported URI {uri}")


class ServerFactory(object):
    @staticmethod
    def get():
        return DbusServer()
