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


class ConsoleMessage:
    """Binary protocol handler between console client and server, to receive and
    send messages in both ways."""

    # ConsoleMessage binary protocol supported commands
    CMD_LOG = 0  # log record
    CMD_BYTES = 1  # raw bytes
    CMD_RAW_ENABLE = 2  # enable terminal raw mode
    CMD_RAW_DISABLE = (
        3  # disable terminal raw mode (ie. restore canonical mode)
    )
    CMD_WINCH = 4  # resize terminal (SIGWINCH)

    def __init__(self, cmd, data=None):
        self.cmd = cmd
        self.data = data
        if self.data:
            self.size = len(self.data)
        else:
            self.size = 0

    @property
    def IS_LOG(self):
        return self.cmd == self.CMD_LOG

    @property
    def IS_BYTES(self):
        return self.cmd == self.CMD_BYTES

    @property
    def IS_RAW_ENABLE(self):
        return self.cmd == self.CMD_RAW_ENABLE

    @property
    def IS_RAW_DISABLE(self):
        return self.cmd == self.CMD_RAW_DISABLE

    @property
    def IS_WINCH(self):
        return self.cmd == self.CMD_WINCH

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
    def read(fd=None, reader=None):
        """Read message either on the given file descriptor or using the given
        reader function, and returns corresponding instanciated ConsoleMessage.
        At least one of fd or reader argument must be provided by caller. The
        reader argument is expected to be a callable accepting size argument.
        If unable to read any byte (ie. EOF is reached), None is returned."""
        assert fd is not None or reader is not None

        # if reader argument is None, use this default reader to read on fd
        def default_reader(size):
            return os.read(fd, size)

        if reader is None:
            reader = default_reader

        buffer = reader(struct.calcsize('HI'))
        if not len(buffer):
            return None  # EOF is reached
        cmd, size = struct.unpack('HI', buffer)
        data = None
        if size:
            data = reader(size)
        return ConsoleMessage(cmd, data)
