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

from pathlib import Path
from datetime import datetime
import os
import logging

from ..protocols.exports import (
    ExportableTaskField,
    ExportableType,
    ExportableField,
)
from ..exec import runcmd
from ..log.handlers import RemoteConsoleHandler
from ..log import logr

logger = logr(__name__)


class TaskIO(ExportableType):
    """Various task input/output channels handler, including log file, output
    fifo, input fifo when interactive and logging handlers."""

    EXFIELDS = {
        ExportableField('interactive', bool),
        ExportableField('fifo_input', Path),
        ExportableField('fifo_output', Path),
        ExportableField('logfile', Path),
    }

    def __init__(self, interactive, input, output, logfile):
        # Defines whether tasks subcommands are launched in interactive mode
        self.interactive = interactive

        self.fifo_output = output
        self.output = None  # fd on output fifo, initialized in open()

        self.fifo_input = input
        # fd on input fifo, initialized in open() in interactive mode
        self.input = None

        self.logfile = logfile
        self.log = None  # file object on log file, initialized in open()

        # logging handlers for the output fifo and the log file, initialized in
        # plug_logger()
        self._fifo_log_handler = None
        self._file_log_handler = None

    def open(self):
        """Open all task IO fd and file objects."""
        self.log = open(self.logfile, 'w+')

        # input fifo is managed in interactive mode only
        if self.interactive:
            if self.fifo_input.exists():
                self.fifo_input.unlink()
            logger.debug("Creating task input fifo %s", self.fifo_input)
            os.mkfifo(self.fifo_input)
            self.fifo_input.chmod(0o770)
            self.input = os.open(self.fifo_input, os.O_RDONLY | os.O_NONBLOCK)

        if self.fifo_output.exists():
            self.fifo_output.unlink()
        logger.debug("Creating task output fifo %s", self.fifo_output)
        os.mkfifo(self.fifo_output)
        self.fifo_output.chmod(0o740)
        self.output = os.open(self.fifo_output, os.O_RDWR)

    def close(self):
        """Close all task IO fd and file objects."""
        os.close(self.output)
        logger.debug("Removing task output fifo %s", self.fifo_output)
        self.fifo_output.unlink()

        if self.interactive:
            os.close(self.input)
            logger.debug("Removing task input fifo %s", self.fifo_input)
            self.fifo_input.unlink()

        self.log.close()

    def plug_logger(self):
        """Plug logging handlers for task output fifo and log file in root
        logger, so worker thread logs are duplicated in remote client console
        and task log file."""
        self._fifo_log_handler = RemoteConsoleHandler(self.output)
        logger.add_thread_handler(self._fifo_log_handler)
        self._file_log_handler = logging.StreamHandler(stream=self.log)
        logger.add_thread_handler(self._file_log_handler)

    def unplug_logger(self):
        """Unplug task logging handlers from root logger."""
        logger.remove_handler(self._fifo_log_handler)
        logger.remove_handler(self._file_log_handler)

    def mute_log(self):
        """Mute task logging handlers. This is usefull when running subcommands,
        to avoid messing logs with command outputs."""
        logger.mute_handler(self._fifo_log_handler)
        logger.mute_handler(self._file_log_handler)

    def unmute_log(self):
        """Unmute previously muted task logging handlers."""
        logger.unmute_handler(self._fifo_log_handler)
        logger.unmute_handler(self._file_log_handler)


class RunnableTask:
    """Abtract runnable task."""

    BASEFIELDS = {
        ExportableTaskField('id', archived=False),
        ExportableTaskField('name'),
        ExportableTaskField('submission', datetime),
        ExportableTaskField('place', Path, archived=False),
        ExportableTaskField('state', archived=False),
        ExportableTaskField('io', TaskIO, archived=False),
    }

    def __init__(
        self,
        task_id,
        place,
        instance,
        state='pending',
        submission=datetime.now(),
        interactive=False,
    ):
        self.name = self.TASK_NAME
        self.id = task_id
        self.place = place
        self.instance = instance
        self.state = state
        self.submission = submission
        self.io = TaskIO(
            interactive,
            self.place.joinpath('input'),
            self.place.joinpath('output'),
            self.place.joinpath('task.log'),
        )

    def prerun(self):

        if self.place.exists():
            logger.warning("Task directory %s already exists", self.place)
        else:
            # create build directory
            logger.info("Creating task directory %s", self.place)
            self.place.mkdir()
            self.place.chmod(0o755)  # be umask agnostic

        # open bi-directional task IO
        self.io.open()

        # duplicate log in interactive output fifo
        self.io.plug_logger()

        # change into running state
        self.state = 'running'

    def run(self):
        raise NotImplementedError

    def postrun(self):
        self.io.unplug_logger()
        self.io.close()

    def terminate(self):
        self.instance.archives_mgr.save_task(self)

    def runcmd(self, cmd, **kwargs):
        """Run command locally and log output in build log file."""
        runcmd(cmd, io=self.io, **kwargs)

    def cruncmd(self, image, cmd, init=False, **kwargs):
        """Run command in container and log output in build log file."""
        self.instance.crun(image, cmd, init=init, io=self.io, **kwargs)
