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
import hashlib
import platform
import os
import pwd
import grp
import tarfile
import copy

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
        while True:
            chunk = fh.read(8192)
            if not chunk:
                break
            f_hash.update(chunk)

    if f_hash.hexdigest() != value:
        raise RuntimeError(
            f"{format} checksum do not match: {f_hash.hexdigest()} != {value}"
        )


def tar_subdir(tar):
    """Returns the name of the subdirectory of the root of the given tarball,
    or raise RuntimeError if not found. The tar argument can either be an opened
    tarfile.TarFile object or a path to a tarball. For the latter, the tarball
    is opened with a recursive call."""
    if type(tar) != tarfile.TarFile:
        with tarfile.open(tar) as _tar:
            return tar_subdir(_tar)
    # search for first member found in root of archive (w/o '/' in name)
    for member in tar.getmembers():
        if '/' not in member.name:
            subdir = member
            break
    if not subdir.isdir():
        raise RuntimeError(f"unable to define tarball {tar.name} subdirectory")
    return subdir.name


def tar_safe_extractall(tar, path):
    """Extract all members from the archive tar to the directory pointed by
    path. This function is largely a copy of Python standard library
    TarFile.extractall() except:
    - It checks for and skips with warning members with absolute path or with
      parent relative directory (ie '..')
    - It does not set attributes (mode, time) of directory pointed by path in
      respect with archive content for root directory. It path already exists,
      its attributes are unmodified. If path does not already exist, its mode is
      set with default mode (ie. in respect to current umask)."""
    directories = []

    for tarinfo in tar:
        # Detect and skip with warning unsafe members
        if tarinfo.name.startswith('/') or '..' in tarinfo.name:
            logger.warning(
                "skipping extraction of unsafe file %s from archive %s",
                tarinfo.name,
                tar.name,
            )
            continue
        if tarinfo.isdir() and tarinfo.name != '.':
            # Extract directories with a safe mode, except for '.'.
            directories.append(tarinfo)
            tarinfo = copy.copy(tarinfo)
            tarinfo.mode = 0o700
        # Do not set_attrs directories, as we will do that further down
        tar.extract(tarinfo, path, set_attrs=not tarinfo.isdir())

    # Reverse sort directories.
    directories.sort(key=lambda a: a.name)
    directories.reverse()

    # Set correct owner, mtime and filemode on directories (except on '.')
    for tarinfo in directories:
        dirpath = os.path.join(path, tarinfo.name)
        tar.chown(tarinfo, dirpath, numeric_owner=False)
        tar.utime(tarinfo, dirpath)
        tar.chmod(tarinfo, dirpath)


def host_architecture():
    return platform.machine()


def current_user():
    """Returns tuple (UID, username) of the currently running process."""
    uid = os.getuid()
    return (uid, pwd.getpwuid(uid)[0])


def current_group():
    """Returns tuple (GID, group) of the currently running process."""
    gid = os.getgid()
    return (gid, grp.getgrgid(gid)[0])


def current_user_group():
    """Returns tuple (UID, username, GID, group) of the currently running
    process."""
    return current_user() + current_group()
