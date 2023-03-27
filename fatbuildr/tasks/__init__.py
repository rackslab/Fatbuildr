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
import socket
import threading
import select

from ..protocols.exports import (
    ExportableTaskField,
    ExportableType,
    ExportableField,
)
from ..exec import runcmd
from ..console import ConsoleMessage
from ..log.handlers import RemoteConsoleHandler
from ..log.formatters import ConsoleFormatter
from ..log import logr

logger = logr(__name__)


class TaskJournal(ExportableType):
    """Handler for task journal, ie. binary file to save task output including
    task logs and sub-commands outputs."""

    EXFIELDS = {
        ExportableField('path', Path),
    }

    def __init__(self, path):
        self.path = path
        self.fh = None

    def open(self):
        logger.debug("Opening journal %s file handler", self.path)
        self.fh = open(self.path, 'bw+')

    def close(self):
        logger.debug("Closing journal %s file handler", self.path)
        self.fh.close()

    def write(self, data):
        self.fh.write(data)

    def replay(self, connection):
        """Reads task journal from the beginning and send it to the incoming
        connection."""
        logger.info("Replaying journal for new incoming connection")

        # Force write buffer flush before reading the file to get all output
        # until now.
        self.fh.flush()

        with open(self.path, 'rb') as fh:
            while True:
                msg = ConsoleMessage.read(fd=fh.fileno())
                if msg is None:
                    break  # stop the loop when EOF is reached
                connection.sendall(msg.raw)


class TaskIO(ExportableType):
    """Various task input/output channels handler, including log file, output
    fifo, input fifo when interactive and logging handlers."""

    EXFIELDS = {
        ExportableField('interactive', bool),
        ExportableField('console', Path),
        ExportableField('journal', TaskJournal),
    }

    def __init__(self, interactive, console, journal):
        # Defines whether tasks subcommands are launched in interactive mode
        self.interactive = interactive

        self.console = console
        self.sock = None  # file object on unix socket, initialized in open()
        self.connections = {}  # clients connections on unix sock

        self.input_r = None
        self.input_w = None
        self.output_r = None
        self.output_w = None
        self.log_r = None
        self.log_w = None

        self.thread = None  # dispatch thread, initialized in dispatch()
        self.stop_dispatch = False  # flag to stop dispatch thread

        # file object on log file, initialized in open()
        self.journal = TaskJournal(journal)

        # logging handlers for the console socket and the log file, initialized
        # in plug_logger()
        self._journal_log_handler = None

    def open(self):
        """Open all task IO fd and file objects."""

        self.journal.open()

        if self.interactive:
            self.input_r, self.input_w = os.pipe2(os.O_CLOEXEC)
        self.output_r, self.output_w = os.pipe2(os.O_CLOEXEC)
        self.log_r, self.log_w = os.pipe2(os.O_CLOEXEC)

        if self.console.exists():
            self.console.unlink()

        logger.debug("Creating console socket %s", self.console)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(str(self.console))
        self.sock.listen(1)
        self.console.chmod(0o770)

    def dispatch(self, task_id):
        """Starts dispatch thread."""
        self.thread = threading.Thread(
            target=self._dispatch, name=f"dispatch-{task_id}"
        )
        self.thread.start()
        logger.debug("Started task io dispatching thread")

    def undispatch(self):
        """Stops dispatch thread."""
        self.stop_dispatch = True  # flag thread to stop
        logger.debug("Dispatching thread stop flag is set")
        self.thread.join()  # wait for thread to actually stop
        logger.debug("Stopped task io dispatching thread")

    def _broadcast(self, data):
        """Broadcast data to all connected console clients."""
        for connection in self.connections.values():
            connection.sendall(data)

    def _dispatch(self):
        """Dispatch task IO. Broadcast task output to connected clients and save
        to journal, transmit input from connected clients to task."""

        # Initialize epoll to multiplex task output and client connections
        epoll = select.epoll()
        epoll.register(self.sock, select.EPOLLIN)
        epoll.register(self.output_r, select.EPOLLIN)
        epoll.register(self.log_r, select.EPOLLIN)

        while True:
            try:
                events = epoll.poll(timeout=1.0)
                if not events and self.stop_dispatch:
                    logger.debug("Dispatch thread detected stop flag")
                    break
                for fd, event in events:
                    if fd == self.sock.fileno():
                        logger.debug("Accepting new client console connection")
                        connection, _ = self.sock.accept()
                        epoll.register(connection.fileno(), select.EPOLLIN)
                        self.connections[connection.fileno()] = connection
                        # Send tasks output from its beginning to new incoming
                        # connection.
                        self.journal.replay(connection)
                    elif event & select.EPOLLHUP:
                        logger.debug("Unregistering client console connection")
                        epoll.unregister(fd)
                        self.connections[fd].close()
                        del self.connections[fd]
                    elif fd == self.log_r:
                        # Broadcast logs to all connected client and save in journal
                        data = os.read(fd, 2048)
                        self._broadcast(data)
                        self.journal.write(data)
                    elif fd == self.output_r:
                        # Broadcast task output to all connected client
                        data = os.read(fd, 2048)
                        # In interactive mode, tty_runcmd() write ConsoleMessage
                        # in output pipe, data can be broadcasted to console
                        # clients without modification. However, in
                        # non-interactive mode _runcmd_noninteractive() writes
                        # sub-commands raw outputs in output pipe. It must be
                        # encapsulated in ConsoleMessage protocol for console
                        # clients and journal.
                        if not self.interactive:
                            data = ConsoleMessage(
                                ConsoleMessage.CMD_BYTES, data
                            ).raw
                        self._broadcast(data)
                        self.journal.write(data)
                    else:
                        # Input data received from client, transmit to task
                        # input pipe when in interactive mode. Thanks to PTY
                        # echo, there is no need to copy user input in TaskIO
                        # journal, it is handled automatically with when data is
                        # read from master fd.
                        data = os.read(fd, 2048)
                        if self.interactive:
                            os.write(self.input_w, data)
                        else:
                            del data  # drop incoming data when not interactive
            except RuntimeError as err:
                logger.error("Error detected: %s", err)
                # Stop while loop and IO processing if an error is detected on fd
                break

        epoll.close()

    def close(self):
        """Close all task IO fd and file objects."""
        self.sock.close()
        logger.debug("Removing console socket %s", self.console)
        self.console.unlink()

        logger.debug("Closing I/O pipes")
        if self.interactive:
            os.close(self.input_w)
            os.close(self.input_r)
        os.close(self.output_w)
        os.close(self.output_r)
        os.close(self.log_w)
        os.close(self.log_r)

        self.journal.close()

    def plug_logger(self):
        """Plug logging handlers for task output fifo and log file in root
        logger, so worker thread logs are duplicated in remote client console
        and task log file."""
        self._journal_log_handler = RemoteConsoleHandler(self.log_w)
        self._journal_log_handler.setFormatter(ConsoleFormatter())
        logger.add_thread_handler(self._journal_log_handler)

    def unplug_logger(self):
        """Unplug task logging handlers from root logger."""
        logger.remove_handler(self._journal_log_handler)

    def mute_log(self):
        """Mute task logging handlers. This is usefull when running subcommands,
        to avoid messing logs with command outputs."""
        logger.mute_handler(self._journal_log_handler)

    def unmute_log(self):
        """Unmute previously muted task logging handlers."""
        logger.unmute_handler(self._journal_log_handler)


class RunnableTask:
    """Abtract runnable task."""

    BASEFIELDS = {
        ExportableTaskField('id', archived=False),
        ExportableTaskField('user'),
        ExportableTaskField('name'),
        ExportableTaskField('submission', datetime),
        ExportableTaskField('place', Path, archived=False),
        ExportableTaskField('state', archived=False),
        ExportableTaskField('io', TaskIO, archived=False),
    }

    def __init__(
        self,
        task_id,
        user,
        place,
        instance,
        state='pending',
        submission=datetime.now(),
        interactive=False,
    ):
        self.name = self.TASK_NAME
        self.id = task_id
        self.user = user
        self.place = place
        self.instance = instance
        self.state = state
        self.submission = submission
        self.io = TaskIO(
            interactive,
            self.place.joinpath('console.sock'),
            self.place.joinpath('task.journal'),
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

        # start IO dispatcher thread
        self.io.dispatch(self.id)

        # duplicate log in interactive output fifo
        self.io.plug_logger()

        # change into running state
        self.state = 'running'

    def run(self):
        raise NotImplementedError

    def postrun(self):
        self.io.unplug_logger()
        self.io.undispatch()  # stop IO dispatch thread
        self.io.close()

    def terminate(self):
        self.instance.archives_mgr.save_task(self)

    def runcmd(self, cmd, **kwargs):
        """Run command locally and log output in build log file."""
        runcmd(cmd, io=self.io, **kwargs)

    def cruncmd(self, image, cmd, init=False, **kwargs):
        """Run command in container and log output in build log file."""
        self.instance.crun(image, cmd, init=init, io=self.io, **kwargs)
