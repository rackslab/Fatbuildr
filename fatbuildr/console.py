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
import pty
import select
from pathlib import Path
import fcntl
import struct
import termios
import signal
import atexit
import threading
import socket

from .log import logr
from .utils import shelljoin

logger = logr(__name__)

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


def emit_log(fd, msg):
    """Write given string message on provided file descriptor using
    ConsoleMessage protocol handler. This is designed to be called by logging
    RemoteConsoleHandler."""
    ConsoleMessage(CMD_LOG, msg.encode()).write(fd)


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
        instanciated ConsoleMessage."""
        buffer = os.read(fd, struct.calcsize('HI'))
        cmd, size = struct.unpack('HI', buffer)
        data = None
        if size:
            data = os.read(fd, size)
        return ConsoleMessage(cmd, data)


class ConsoleCompletedProcess:
    """Tiny class to mimic tiny subset of subprocess.CompletedProcess as
    expected by tty_runcmd() consumers."""

    def __init__(self, returncode):
        self.returncode = returncode


def tty_runcmd(cmd, io, **kwargs):
    """Runs command cmd with stdin, stdout and stderr attached to a newly
    spawned pseudo-terminal (aka. PTY). The command is actually executed in a
    forked subprocess. The function then copies subprocess output (stdout,
    stderr) to the given task output (using ConsoleMessage protocol handler)
    and, in the opposite way, it copies task io input to subprocess stdin,
    through PTY master fd. The function also capture ConsoleMessage WINCH sent
    by remote console client and calls corresponding ioctl() to send SIGWINCH
    signal to the subprocess controlled by the terminal.
    A thread is spawned to capture the subprocess return code. The function
    returns a ConsoleCompletedProcess object with this return code.

    This function is supposed to be indirectly called by a work thread of
    fatbuildrd.
    """

    logger.debug("Running command in interactive mode: %s", shelljoin(cmd))

    # Tell remote console client to set terminal in raw mode
    ConsoleMessage(CMD_RAW_ENABLE).write(io.output_w)
    # Mute task logging records in log file and console channel to avoid messing
    # with command raw output.
    io.mute_log()

    (pid, master) = pty.fork()

    if pid == 0:
        # Child process initialize optional environments variables provided by
        # caller and executes the command.
        if 'env' in kwargs:
            for key, value in kwargs['env'].items():
                os.environ[key] = value
        cmd_s = [str(item) for item in cmd]
        os.execlp(cmd_s[0], *cmd_s)

    # ConsoleCompletedProcess returned value. It is initialized by wait_child
    # thread when child process return code is captured.
    proc = None

    # Thread inner function to capture subprocess return code
    def wait_child(pid):
        nonlocal proc
        logger.debug("Thread start waiting for PID %d", pid)
        status = os.waitpid(pid, 0)[1]
        proc = ConsoleCompletedProcess(os.waitstatus_to_exitcode(status))
        logger.debug("Captured PID %d return code %d", pid, proc.returncode)

    # Start background thread to capture child return code
    wait_thread = threading.Thread(target=wait_child, args=(pid,))
    wait_thread.start()

    # Initialize epoll to multiplex subprocess and task io input/ouputs
    epoll = select.epoll()
    epoll.register(master, select.EPOLLIN)
    epoll.register(io.input_r, select.EPOLLIN)

    while True:
        try:
            events = epoll.poll()
            for fd, event in events:
                if event & select.EPOLLHUP:
                    # A registered fd triggers EPOLLHUP event is certainly due
                    # to the master fd being close because the subprocess
                    # command has exited and the connected PTY is destroyed by
                    # the kernel. In this case, raise RuntimeError and stop
                    # processing.
                    raise RuntimeError(f"Hang up detected on fd {fd}")
                if fd == io.input_r:
                    # Input from remote console clients is received, read data
                    # with ConsoleMessage protocol handler.
                    msg = ConsoleMessage.read(fd)
                    if msg.cmd == CMD_WINCH:
                        # SIGWINCH command is received, call approriate ioctl on
                        # PTY master fd so the kernel send SIGWINCH signal to
                        # the process controlled by the slave side of the
                        # terminal.
                        (rows, cols) = struct.unpack('HH', msg.data)
                        size = struct.pack('HHHH', rows, cols, 0, 0)
                        fcntl.ioctl(master, termios.TIOCSWINSZ, size)
                        logger.debug(
                            "Sent ioctl() TIOCGWINSZ %d rows x %d cols to PTY master",
                            rows,
                            cols,
                        )
                    elif msg.cmd == CMD_BYTES:
                        # The remote console clients sent bytes received on its
                        # stdin, recopy without modification on PTY master so
                        # the controlled process receives the input on its
                        # stdin.
                        os.write(master, msg.data)
                elif fd == master:
                    # Data are available for reading on PTY master fd, this is
                    # subprocess output. The read bytes are redirected to task
                    # io output pipe with ConsoleMessage protocol handler, for
                    # remote console clients and to be saved in task journal.
                    data = os.read(fd, 1024)
                    ConsoleMessage(CMD_BYTES, data).write(io.output_w)
                else:
                    raise RuntimeError(
                        "Data is available on excepted fd %d", fd
                    )
        except RuntimeError as err:
            logger.error("Error detected: %s", err)
            # Stop while loop and IO processing if an error is detected on fd
            break

    os.close(master)
    epoll.close()

    # Tell remote console client to restore terminal in canonical mode
    ConsoleMessage(CMD_RAW_DISABLE).write(io.output_w)
    # Unmute task logging records in journal file and remote console channel
    io.unmute_log()

    logger.debug("Waiting for child return code thread")
    wait_thread.join()

    logger.debug("Stop running interactive command")

    return proc


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
                            ConsoleMessage(CMD_WINCH, get_term_size()).raw
                        )
                    else:
                        logger.warning(f"Received unknown signal: {str(data)}")
                elif fd == sys.stdin.fileno():
                    # Input has been provided by user on attached terminal, send
                    # bytes to remote task terminal with ConsoleMessage protocol
                    # handler.
                    data = os.read(fd, 100)
                    connection.send(ConsoleMessage(CMD_BYTES, data).raw)
                else:
                    # Remote server console has sent data, read the command with
                    # ConsoleMessage protocol handler.
                    msg = ConsoleMessage.receive(connection)
                    if msg.cmd == CMD_RAW_ENABLE:
                        # Set attached terminal in raw mode and immediately send
                        # current size to avoid remote terminal using default
                        # (small) size.
                        set_raw()
                        connection.send(
                            ConsoleMessage(CMD_WINCH, get_term_size()).raw
                        )
                    elif msg.cmd == CMD_RAW_DISABLE:
                        # Restore attached terminal in canonical mode.
                        unset_raw()
                    elif msg.cmd == CMD_BYTES:
                        # The remote process has produced output, write raw
                        # bytes on stdout and flush immediately to avoid
                        # buffering.
                        sys.stdout.buffer.write(msg.data)
                        sys.stdout.flush()
                    elif msg.cmd == CMD_LOG:
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
        if msg.cmd == CMD_BYTES:
            # The remote process has produced output, write raw
            # bytes on stdout and flush immediately to avoid
            # buffering.
            sys.stdout.buffer.write(msg.data)
            sys.stdout.flush()
        elif msg.cmd == CMD_LOG:
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
