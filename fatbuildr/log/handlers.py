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

import logging

from ..console import emit_log


class RemoteConsoleHandler(logging.Handler):
    """Logging handler to send log records to remote console client."""

    def __init__(self, fd):
        """The initialize takes in argument the open file descriptor to the
        remote console client whose log records are sent."""
        super().__init__()
        self.fd = fd

    def emit(self, record):
        """Overrides logging.Handler emit() to send messages using
        ConsoleMessage protocol handler."""
        # Calls to self.format() and error handling are shameless copy from
        # logging.Handler.emit().
        try:
            emit_log(self.fd, self.format(record))
        except Exception:
            self.handleError(record)
