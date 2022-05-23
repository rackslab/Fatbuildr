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
import sys
import tty
import fcntl
import select
import struct
import termios
import signal
import atexit
import socket

from . import ConsoleMessage
from ..tasks import TaskJournal
from ..log import logr

logger = logr(__name__)


class TerminatedTask(Exception):
    """Exception raised on client side on remote task normal termination
    detection, to break the double nested processing loop."""

    pass


def tty_client_console(io):
    """Connects to the given remote task IO running on server side, as run by
    tty_runcmd(). It catches attached terminal input and signals (SIGWINCH) and
    sends everything to remote terminal through task IO output. In the opposite
    way, it prints on stdout all remote terminal output and remote server task
    logs. It also set attached terminal in raw and canonical modes, following
    servers instructions.

    This function is supposed to be indirectly called by fatbuildrctl in user
    terminal.
    """

    # Save user terminal attributes, so they can be restored
    user_attr = termios.tcgetattr(sys.stdin)

    # Inner function registered atexit when terminal is set in raw mode, to the
    # terminal can be restored in canonical mode with all user attributes when
    # client is terminated.
    def restore_term():
        termios.tcsetattr(sys.stdin, termios.TCSANOW, user_attr)
        logger.debug("Restored user terminal attributes")

    # Returns bytes with attached terminal current size, ready to be sent by
    # ConsoleMessage protocol handler along with CMD_WINCH command.
    def get_term_size():
        cols, rows = os.get_terminal_size(0)
        return struct.pack('HH', rows, cols)

    # Set user attached terminal in raw mode, and register restore function in
    # case of terminated client.
    def set_raw():
        logger.debug("Setting terminal in raw mode")
        atexit.register(restore_term)
        tty.setraw(sys.stdin, termios.TCSANOW)

    # Restore terminal in canonical mode, and unregister restore function in
    # case of terminated client.
    def unset_raw():
        restore_term()
        atexit.unregister(restore_term)

    # Connect to task console socket
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.connect(str(io.console))
    logger.debug(f"Connected to console socket %s", io.console)

    # Create signal pipe to process signals with epoll. No-op handler is
    # assigned to SIGWINCH signal so the thread can receive it.
    signal.signal(signal.SIGWINCH, lambda x, y: None)
    pipe_r, pipe_w = os.pipe()
    flags = fcntl.fcntl(pipe_w, fcntl.F_GETFL, 0)
    flags = flags | os.O_NONBLOCK
    fcntl.fcntl(pipe_w, fcntl.F_SETFL, flags)
    signal.set_wakeup_fd(pipe_w)
    logger.debug(f"Signal pipe FD: {str(pipe_r)}")

    # Initialize epoll to multiplex attached terminal and remote task IO
    epoll = select.epoll()
    epoll.register(connection, select.EPOLLIN)
    epoll.register(sys.stdin.fileno(), select.EPOLLIN)
    epoll.register(pipe_r, select.EPOLLIN)

    while True:
        try:
            events = epoll.poll()
            for fd, event in events:
                if event & select.EPOLLHUP:
                    # One registered fd triggers EPOLLHUP event. This is very
                    # probably due to the remote task IO having been closed
                    # because the task has reached its end. Raise a RuntimeError
                    # to break the loop and processing.
                    raise RuntimeError(f"Hang up detected on fd {fd}")
                if fd == pipe_r:
                    # Signal has been received. If SIGWINCH, send current
                    # terminal size with ConsoleMessage protocol handler to
                    # remote terminal. For other unexpected signal, log an
                    # error.
                    data = os.read(fd, 100)
                    if int.from_bytes(data, sys.byteorder) == signal.SIGWINCH:
                        connection.send(
                            ConsoleMessage(
                                ConsoleMessage.CMD_WINCH, get_term_size()
                            ).raw
                        )
                    else:
                        logger.warning(f"Received unknown signal: {str(data)}")
                elif fd == sys.stdin.fileno():
                    # Input has been provided by user on attached terminal, send
                    # bytes to remote task terminal with ConsoleMessage protocol
                    # handler.
                    data = os.read(fd, 100)
                    connection.send(
                        ConsoleMessage(ConsoleMessage.CMD_BYTES, data).raw
                    )
                else:
                    # Remote server console has sent data, read the command with
                    # ConsoleMessage protocol handler.
                    msg = ConsoleMessage.receive(connection)
                    if msg.IS_RAW_ENABLE:
                        # Set attached terminal in raw mode and immediately send
                        # current size to avoid remote terminal using default
                        # (small) size.
                        set_raw()
                        connection.send(
                            ConsoleMessage(
                                ConsoleMessage.CMD_WINCH, get_term_size()
                            ).raw
                        )
                    elif msg.IS_RAW_DISABLE:
                        # Restore attached terminal in canonical mode.
                        unset_raw()
                    elif msg.IS_BYTES:
                        # The remote process has produced output, write raw
                        # bytes on stdout and flush immediately to avoid
                        # buffering.
                        sys.stdout.buffer.write(msg.data)
                        sys.stdout.flush()
                    elif msg.IS_LOG:
                        # The remote server sent log record, print it on stdout.
                        entry = msg.data.decode()
                        print(f"LOG: {entry}")
                        if entry.startswith("Task failed") or entry.startswith(
                            "Task succeeded"
                        ):
                            logger.debug(f"Remote task is over, leaving")
                            # Raise an exception as there is no way to break the
                            # while loop from here.
                            raise TerminatedTask
                    else:
                        # Warn for unexpected command.
                        logger.warning(
                            "Unknown console message command %s", msg.cmd
                        )
        except TerminatedTask:
            # Remote task is terminated normally, just leave the loop silently.
            break
        except RuntimeError as err:
            # If any error occurs during IO processing, restore attached
            # terminal in canonical mode with user attribute, warn user and
            # break the processing loop.
            unset_raw()
            logger.warning(f"{type(err)} detected: {err}")
            break

    # Close all open fd and epoll
    connection.close()
    os.close(pipe_r)
    os.close(pipe_w)
    epoll.close()


def console_client(io):
    """Connects to the given remote task IO running on server side. It prints on
    stdout all remote terminal output and remote server task logs.

    This function is supposed to be indirectly called by fatbuildrctl in user
    terminal.
    """

    # Connect to task console socket
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.connect(str(io.console))
    logger.debug(f"Connected to console socket %s", io.console)

    while True:
        # Remote server console has sent data, read the command with
        # ConsoleMessage protocol handler.
        msg = ConsoleMessage.receive(connection)
        if msg.IS_BYTES:
            # The remote process has produced output, write raw
            # bytes on stdout and flush immediately to avoid
            # buffering.
            sys.stdout.buffer.write(msg.data)
            sys.stdout.flush()
        elif msg.IS_LOG:
            # The remote server sent log record, print it on stdout.
            entry = msg.data.decode()
            print(f"LOG: {entry}")
            if entry.startswith("Task failed") or entry.startswith(
                "Task succeeded"
            ):
                logger.debug(f"Remote task is over, leaving")
                # Break the processing loop
                break
        else:
            # Warn for unexpected command.
            logger.warning("Unknown console message command %s", msg.cmd)

    # Close all open fd and epoll
    connection.close()


def console_reader(io):
    """Read a task journal and prints on stdout this task output and remote
    server task logs.

    This function is supposed to be indirectly called by fatbuildrctl in user
    terminal."""
    journal = TaskJournal(io.journal.path)

    for msg in journal.messages():
        if msg.IS_BYTES:
            # The remote process has produced output, write raw
            # bytes on stdout and flush immediately to avoid
            # buffering.
            sys.stdout.buffer.write(msg.data)
            sys.stdout.flush()
        elif msg.IS_LOG:
            # The remote server sent log record, print it on stdout.
            entry = msg.data.decode()
            print(f"LOG: {entry}")
            if entry.startswith("Task failed") or entry.startswith(
                "Task succeeded"
            ):
                logger.debug(f"Remote task is over, leaving")
                # Break the processing loop
                break
