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
import pty
import select
import fcntl
import struct
import termios
import threading

from . import ConsoleMessage
from ..log import logr
from ..utils import shelljoin

logger = logr(__name__)


def emit_log(fd, msg):
    """Write given string message on provided file descriptor using
    ConsoleMessage protocol handler. This is designed to be called by logging
    RemoteConsoleHandler."""
    ConsoleMessage(ConsoleMessage.CMD_LOG, msg.encode()).write(fd)


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
    ConsoleMessage(ConsoleMessage.CMD_RAW_ENABLE).write(io.output_w)
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
                    if msg.IS_WINCH:
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
                    elif msg.IS_BYTES:
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
                    ConsoleMessage(ConsoleMessage.CMD_BYTES, data).write(
                        io.output_w
                    )
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
    ConsoleMessage(ConsoleMessage.CMD_RAW_DISABLE).write(io.output_w)
    # Unmute task logging records in journal file and remote console channel
    io.unmute_log()

    logger.debug("Waiting for child return code thread")
    wait_thread.join()

    logger.debug("Stop running interactive command")

    return proc
