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


class ANSIStyle():

    def __init__(self, fg, bg=None):
        self.fg = fg
        self.bg = bg

    @property
    def start(self):
        bg_s = ""
        if self.bg is not None:
            bg_s = "\033[48;5;%sm" % (self.bg)
        return bg_s + "\033[38;5;%sm" % (self.fg)

    @property
    def end(self):
        return "\033[0;0m"


class TTYFormatter(logging.Formatter):

    LEVEL_STYLES = {
        logging.CRITICAL: ANSIStyle(fg=15, bg=160), # white on red
        logging.ERROR: ANSIStyle(fg=160), # red
        logging.WARNING: ANSIStyle(fg=208), # orange
        logging.INFO: ANSIStyle(fg=28), # dark green
        logging.DEBUG: ANSIStyle(fg=62), # light mauve
        logging.NOTSET: ANSIStyle(fg=8), # grey
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
                where=record.name + ':' + str(record.lineno)
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


class BuildlogFilter(logging.Filter):

    def filter(self, record):
        if record.threadName == 'builder':
            return 1
        return 0


class Log(logging.Logger):

    def __init__(self, name):
        super().__init__(name)
        self._file_handler = None  # used for file duplication

    def has_debug(self):
        return self.isEnabledFor(logging.DEBUG)

    def formatter(self, debug):
        if self.name == 'fatbuildr.cli.fatbuildrd':
            return DaemonFormatter(debug)
        if self.name == 'fatbuildr.cli.fatbuildrweb':
            return DaemonFormatter(debug)
        elif self.name == 'fatbuildr.cli.fatbuildrctl':
            return TTYFormatter(debug)
        else:
            raise RuntimeError("Unable to define log formatter for module %s"
                               % (self.name))

    def setup(self, debug: bool):
        if debug:
            logging_level = logging.DEBUG
        else:
            logging_level = logging.INFO

        _root_logger = logging.getLogger()
        _root_logger.setLevel(logging_level)
        _handler = logging.StreamHandler()
        _handler.setLevel(logging_level)
        _formatter = self.formatter(debug)
        _handler.setFormatter(_formatter)
        _filter = logging.Filter('fatbuildr')  # filter out all libs logs
        _handler.addFilter(_filter)
        _root_logger.addHandler(_handler)

    def ensure_debug(self):
        _root_logger = logging.getLogger()
        # do nothing if already at debug
        if _root_logger.isEnabledFor(logging.DEBUG):
            return
        _root_logger.setLevel(level=logging.DEBUG)
        _formatter = self.formatter(debug=True)
        # set formatter and log level for all handlers
        for handler in _root_logger.handlers:
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(_formatter)

    def add_file(self, path):
        self._file_handler = logging.FileHandler(path)
        _filter = BuildlogFilter()
        self._file_handler.addFilter(_filter)
        logging.getLogger().addHandler(self._file_handler)

    def del_file(self):
        assert self._file_handler is not None
        logging.getLogger().removeHandler(self._file_handler)
        self._file_handler = None


def logr(name):
    """Instanciate Log by setting logging.setLoggerClass using
       logging.getLogger() so Python logging module can do all its Loggers
       registration. """
    logging.setLoggerClass(Log)
    return logging.getLogger(name)
