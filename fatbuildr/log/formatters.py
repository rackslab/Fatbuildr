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


class ANSIStyle:
    def __init__(self, fg, bg=None):
        self.fg = fg
        self.bg = bg

    @property
    def start(self):
        bg_s = ""
        if self.bg is not None:
            bg_s = f"\033[48;5;{self.bg}m"
        return bg_s + f"\033[38;5;{self.fg}m"

    @property
    def end(self):
        return "\033[0;0m"


class TTYFormatter(logging.Formatter):

    LEVEL_STYLES = {
        logging.CRITICAL: ANSIStyle(fg=15, bg=160),  # white on red
        logging.ERROR: ANSIStyle(fg=160),  # red
        logging.WARNING: ANSIStyle(fg=208),  # orange
        logging.INFO: ANSIStyle(fg=28),  # dark green
        logging.DEBUG: ANSIStyle(fg=62),  # light mauve
        logging.NOTSET: ANSIStyle(fg=8),  # grey
    }

    def __init__(self, debug=False):
        super().__init__("%(message)s")
        self.debug = debug

    def format(self, record):

        _msg = record.getMessage()
        style = TTYFormatter.LEVEL_STYLES[record.levelno]
        prefix = ''
        if self.debug:
            prefix = "{level:8s}⸬{where:30s} ↦ ".format(
                level='[' + record.levelname + ']',
                where=record.name + ':' + str(record.lineno),
            )
        elif record.levelno > logging.INFO:
            # prefix with level if over info
            prefix = "{level} ⸬ ".format(level=record.levelname)

        return style.start + prefix + _msg + style.end


class DaemonFormatter(logging.Formatter):
    def __init__(self, debug=True):
        if debug:
            _fmt = '%(threadName)s: [%(levelname)s] %(name)s %(message)s'
        else:
            _fmt = '%(threadName)s: [%(levelname)s] %(message)s'
        super().__init__(_fmt)
