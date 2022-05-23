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

import subprocess

from .utils import shelljoin
from .console.server import tty_runcmd
from .log import logr

logger = logr(__name__)


def runcmd(cmd, io=None, **kwargs):
    """Run command cmd. The io parameter is optional, when given it must be a
    TaskIO object. The kwargs are given unmodified to subprocess calls in
    non-interactive mode (ie. when io.interactive is not True). Only a subset of
    subprocess arguments are supported in interactive mode."""
    if io and io.interactive:
        proc = tty_runcmd(cmd, io, **kwargs)
    else:
        proc = _runcmd_noninteractive(cmd, io, **kwargs)
    if proc.returncode:
        error = (
            f"Command {shelljoin(cmd)} failed with exit code "
            f"{proc.returncode}"
        )
        if io is None:
            error += f": {proc.stderr.decode()}"
        raise RuntimeError(error)
    return proc


def _runcmd_noninteractive(cmd, io, **kwargs):
    logger.debug("Running command: %s", shelljoin(cmd))
    if io is None:
        return subprocess.run(cmd, capture_output=True, **kwargs)
    else:
        return subprocess.run(
            cmd, stdout=io.output_w, stderr=io.output_w, **kwargs
        )
