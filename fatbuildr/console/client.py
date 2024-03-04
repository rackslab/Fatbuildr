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
import logging

import requests

from . import ConsoleMessage
from ..log import logr
from ..log.formatters import LOG_LEVEL_ANSI_STYLES, TASK_LOG

logger = logr(__name__)


def _is_task_end_log_entry(entry):
    """Returns True if the given log entry indicates task end, False
    otherwise."""
    msg = entry.split(':')[1]
    if msg.startswith("Task failed") or msg.startswith("Task succeeded"):
        return True
    return False


def _is_task_end_msg(msg):
    """Returns True if the given ConsoleMessage indicates task end, False
    otherwise."""
    if msg.IS_LOG:
        # The remote server sent log record, print it on stdout.
        entry = msg.data.decode()
        return _is_task_end_log_entry(entry)
    return False


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
    logger.debug("Connected to console socket %s", io.console)

    # Unix socket connection reader for ConsoleMessage.read()
    def reader(size):
        data = connection.recv(size)
        # retry until enough data has been received
        while len(data) < size:
            missing = size - len(data)
            data += connection.recv(missing)
        return data

    # Create signal pipe to process signals with epoll. No-op handler is
    # assigned to SIGWINCH signal so the thread can receive it.
    signal.signal(signal.SIGWINCH, lambda x, y: None)
    pipe_r, pipe_w = os.pipe()
    flags = fcntl.fcntl(pipe_w, fcntl.F_GETFL, 0)
    flags = flags | os.O_NONBLOCK
    fcntl.fcntl(pipe_w, fcntl.F_SETFL, flags)
    signal.set_wakeup_fd(pipe_w)
    logger.debug("Signal pipe FD: %s", str(pipe_r))

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
                        logger.warning("Received unknown signal: %s", str(data))
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
                    msg = ConsoleMessage.read(reader=reader)
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
                        tty_console_renderer_raw(msg.data)
                    elif msg.IS_LOG:
                        # The remote server sent log record, print it on stdout.
                        entry = msg.data.decode()
                        tty_console_renderer_log(entry)
                        if _is_task_end_log_entry(entry):
                            logger.debug("Remote task is over, leaving")
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
            logger.warning("%s detected: %s", str(type(err)), str(err))
            break

    # Close all open fd and epoll
    connection.close()
    os.close(pipe_r)
    os.close(pipe_w)
    epoll.close()


def console_unix_client(io, binary):
    """Connects to the given remote task IO running on server side using task
    console Unix socket and generates the ConsoleMessage received on the socket.
    If binary argument is False, ConsoleMessage are generated as objects.
    Otherwise they are generated in bytes.

    This function is supposed to be called for running tasks only."""

    # Connect to task console socket
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.connect(str(io.console))
    logger.debug("Connected to console socket %s", io.console)

    def reader(size):
        data = connection.recv(size)
        # retry until enough data has been received
        while len(data) < size:
            missing = size - len(data)
            data += connection.recv(missing)
        return data

    yield from _console_generator(binary, reader=reader)

    # Close all open fd and epoll
    connection.close()


def console_reader(io, binary):
    """Read the given task I/O journal and generates the ConsoleMessage received
    on the socket. If binary argument is False, ConsoleMessage are generated as
    objects. Otherwise they are generated in bytes.

    This function is supposed to be called for archived tasks only."""
    with open(io.journal.path, 'rb') as fh:
        yield from _console_generator(binary, fd=fh.fileno())


def console_http_client(response):
    """Reads and generates the ConsoleMessage available in the given HTTP
    response object."""

    iterator = response.iter_content(chunk_size=32)
    buffer = next(iterator)

    def reader(size):
        # The chunk size of the response content generator cannot be changed
        # while reading streamed data. The data are placed into a buffer.
        # Depending on the required read size, the data is extracted from the
        # beginning of the buffer or read from the generator until the expected
        # size is reached.
        nonlocal buffer
        chunk = bytes()
        while size:
            if len(buffer) >= size:
                chunk += buffer[:size]
                buffer = buffer[size:]
                size = 0
            else:
                chunk += buffer
                size -= len(buffer)
                try:
                    buffer = next(iterator)
                except StopIteration:
                    logger.warn(
                        "Unexpected end of task output from HTTP server"
                    )
                    # empty binary result stops ConsoleMessage.read() processing
                    return b""
                except requests.exceptions.ChunkedEncodingError as err:
                    logger.warn(
                        "Unable to read task output from HTTP request due to "
                        "chunk encoding error"
                    )
                    logger.debug("Chunk encoding error details: %s", err)
        return chunk

    yield from _console_generator(False, reader=reader)


def _console_generator(binary, **kwargs):
    """The real shared internal ConsoleMessage generator."""

    while True:
        # Remote server console has sent data, read the command with
        # ConsoleMessage protocol handler.
        msg = ConsoleMessage.read(**kwargs)
        if msg is None:
            # Reached EOF, break the processing loop
            break
        if binary:
            yield msg.raw
        else:
            yield msg
        if _is_task_end_msg(msg):
            # Break the processing loop
            break


def tty_console_renderer(console_generator):
    """Iterates over on of the above ConsoleMessage generator (not in binary
    mode) and print task output on terminal stdout.

    This function is supposed to be called by fatbuildrctl."""
    for msg in console_generator:
        if msg.IS_BYTES:
            # The remote process has produced output, write raw
            # bytes on stdout and flush immediately to avoid
            # buffering.
            tty_console_renderer_raw(msg.data)
        elif msg.IS_LOG:
            # The remote server sent log record, print it on stdout.
            entry = msg.data.decode()
            tty_console_renderer_log(entry)


def tty_console_renderer_raw(data):
    """Write task raw output on user terminal stdout."""
    sys.stdout.buffer.write(data)
    sys.stdout.flush()


def tty_console_renderer_log(entry):
    """Parses task log entry as formatted by ConsoleFormatter and write it on
    user terminal stdout."""
    level, msg = entry.split(':', 1)
    level = int(level)
    # If the task remote log entry is at debug level and debug is level is
    # disabled in local logger, skip the log entry.
    if not logger.has_debug() and level == logging.DEBUG:
        return
    log_style = LOG_LEVEL_ANSI_STYLES[TASK_LOG]
    level_style = LOG_LEVEL_ANSI_STYLES[level]
    print(
        f"{log_style.start} ⚬ {log_style.end}"
        f"{level_style.start}{logging.getLevelName(level)}{level_style.end}"
        f"{log_style.start}: {msg}{log_style.end}"
    )
