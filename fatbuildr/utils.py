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

import shlex
import subprocess

from .log import logr

logger = logr(__name__)


class Singleton(type):
    __instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in Singleton.__instances:
            Singleton.__instances[cls] = super(Singleton, cls).__call__(
                *args, **kwargs
            )
        return Singleton.__instances[cls]


def shelljoin(cmd):
    return " ".join(shlex.quote(str(x)) for x in cmd)


def runcmd(cmd, log=None, **kwargs):
    logger.debug("Running command: %s", shelljoin(cmd))
    if log is None:
        proc = subprocess.run(cmd, capture_output=True, **kwargs)
    else:
        proc = subprocess.run(cmd, stdout=log, stderr=log, **kwargs)
    if proc.returncode:
        error = (
            f"Command {shelljoin(cmd)} failed with exit code "
            f"{proc.returncode}"
        )
        if log is None:
            error += f": {proc.stderr.decode()}"
        raise RuntimeError(error)
    return proc
