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
import hashlib
import platform

import requests

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
    return " ".join(shlex.quote(str(x).replace('\n', '\\n')) for x in cmd)


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


def dl_file(url, path):
    #  actual download and write in cache
    logger.debug("Downloading tarball %s and save in %s", url, path)
    dl = requests.get(url, allow_redirects=True)
    open(path, 'wb').write(dl.content)


def hasher(format):
    """Return the hashlib object corresponding to the given hash format."""
    if format == 'sha1':
        return hashlib.sha1()
    elif format == 'sha256':
        return hashlib.sha256()
    else:
        raise RuntimeError(f"Unsupported hash format {format}")


def verify_checksum(path, format, value):
    f_hash = hasher(format)

    with open(path, "rb") as fh:
        while chunk := fh.read(8192):
            f_hash.update(chunk)

    if f_hash.hexdigest() != value:
        raise RuntimeError(
            f"{format} checksum do not match: {f_hash.hexdigest()} != {value}"
        )


def tar_subdir(tar):
    """Returns the name of the subdirectory of the root of the given tarball,
    or raise RuntimeError if not found."""
    subdir = tar.getmembers()[0]
    if not subdir.isdir():
        raise RuntimeError(f"unable to define tarball {tar.name} subdirectory")
    return subdir.name


def host_architecture():
    return platform.machine()
