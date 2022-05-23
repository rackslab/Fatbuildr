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
import struct

# For references, some great and useful articles regarding TTY processing, PTY
# and SIGWINCH:
#
#   http://www.linusakesson.net/programming/tty/index.php
#   http://www.rkoucha.fr/tech_corner/pty_pdip.html
#   http://www.rkoucha.fr/tech_corner/sigwinch.html

# ConsoleMessage binary protocol supported commands
CMD_LOG = 0  # log record
CMD_BYTES = 1  # raw bytes
CMD_RAW_ENABLE = 2  # enable terminal raw mode
CMD_RAW_DISABLE = 3  # disable terminal raw mode (ie. restore canonical mode)
CMD_WINCH = 4  # resize terminal (SIGWINCH)


class ConsoleMessage:
    """Binary protocol handler between console client and server, to receive and
    send messages in both ways."""

    def __init__(self, cmd, data=None):
        self.cmd = cmd
        self.data = data
        if self.data:
            self.size = len(self.data)
        else:
            self.size = 0

    @property
    def raw(self):
        """Returns ConsoleMessage raw bytes."""
        buffer = struct.pack('HI', self.cmd, self.size)
        if self.data:
            buffer += self.data
        return buffer

    def write(self, fd):
        """Send ConsoleMessage to given file descriptor."""
        os.write(fd, self.raw)

    @staticmethod
    def receive(connection):
        """Receive message on given socket connection and returns corresponding
        instanciated ConsoleMessage."""
        buffer = connection.recv(struct.calcsize('HI'))
        cmd, size = struct.unpack('HI', buffer)
        data = None
        if size:
            data = connection.recv(size)
        return ConsoleMessage(cmd, data)

    @staticmethod
    def read(fd):
        """Read message on given file description and returns corresponding
        instanciated ConsoleMessage. If unable to read any byte on fd (ie. EOF
        is reached), None is returned."""
        buffer = os.read(fd, struct.calcsize('HI'))
        if not len(buffer):
            return None  # EOF is reached
        cmd, size = struct.unpack('HI', buffer)
        data = None
        if size:
            data = os.read(fd, size)
        return ConsoleMessage(cmd, data)
