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

import os
import socket

from .log import logr

logger = logr(__name__)


class ServiceManager:
    def __init__(self):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        addr = os.getenv('NOTIFY_SOCKET')
        logger.debug("Found NOTIFY_SOCKET: %s" % (addr))
        self.socket.connect(addr)

    def _notify(self, state):
        self.socket.sendall(state.encode())

    def notify_watchdog(self):
        logger.debug("Notifying service manager for watchdog")
        self._notify('WATCHDOG=1')

    def notify_stop(self):
        logger.debug("Notifying service manager for stopping")
        self._notify('STOPPING=1')
