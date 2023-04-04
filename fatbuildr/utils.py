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
import mimetypes
import time
import zipfile

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


def zip_subdir(zip_fh):
    """Returns the name of the subdirectory of the root of the given zip file,
    or raise RuntimeError if not found. The zip_fh argument can either be an
    opened zipfile.ZipFile object or a path to a zip file. For the latter, the
    zip file is opened with a recursive call."""
    if type(zip_fh) != zipfile.ZipFile:
        with zipfile.ZipFile(zip_fh) as _zip:
            return zip_subdir(_zip)
    for member in zip_fh.infolist():
        if '/' not in member.filename[:-1]:
            subdir = member
            break
    if not subdir.is_dir():
        raise RuntimeError(
            f"unable to define zip file {zip_fh.filename} subdirectory"
        )
    return subdir.filename[:-1]


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


def tar_has_single_toplevel(tar):
    """Returns True if the tarball pointed by the given path contains a single
    element at its top-level, and False otherwise."""
    already_found = False
    with tarfile.open(tar) as _tar:
        for member in _tar.getmembers():
            if '/' not in member.name:
                if already_found:
                    return False
                already_found = True
    return True


def tar_safe_extractall(tar, path, strip):
    """Extract all members from the archive tar to the directory pointed by
    path. This function is largely a copy of Python standard library
    TarFile.extractall() except:
    - It checks for and skips with warning members with absolute path or with
      parent relative directory (ie '..')
    - It does not set attributes (mode, time) of directory pointed by path in
      respect with archive content for root directory. If path already exists,
      its attributes are unmodified. If path does not already exist, its mode is
      set with default mode (ie. in respect to current umask).
    The strip argument can be used with a value above 0 to remove the first n
    elements of members path. The tarball members with paths below this level
    are skipped with a warning message."""
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
        if strip:
            if tarinfo.name.count('/') < strip:
                logger.info("skipping extraction of file %s due to stripping")
                continue
            extracted_path = os.path.join(
                path, tarinfo.name.split('/', strip)[-1]
            )
        else:
            extracted_path = os.path.join(path, tarinfo.name)
        if tarinfo.isdir() and tarinfo.name != '.':
            # Extract directories with a safe mode, except for '.'.
            directories.append((tarinfo, extracted_path))
            tarinfo = copy.copy(tarinfo)
            tarinfo.mode = 0o700
        # Do not set_attrs directories, as we will do that further down.
        # TarFile._extract_member() hidden method is used instead of
        # TarFile.extract() because we need to control the path of the
        # extracted file.
        tar._extract_member(
            tarinfo, extracted_path, set_attrs=not tarinfo.isdir()
        )

    # Reverse sort directories.
    directories.sort(key=lambda a: a[1])
    directories.reverse()

    # Set correct owner, mtime and filemode on directories (except on '.')
    for tarinfo, extracted_path in directories:
        tar.chown(tarinfo, extracted_path, numeric_owner=False)
        tar.utime(tarinfo, extracted_path)
        tar.chmod(tarinfo, extracted_path)


def is_zip(path):
    """Returns True if the given path is a zip file."""
    return mimetypes.guess_type(str(path))[0] == 'application/zip'


def zip2tar(zip_path, tar_path):
    """Convert the given zip file to a tarball with xz compression. The zip file
    metadata (size/mtime) are preserved so the generated files are binary
    reproducible."""
    logger.info("Converting zip file %s to tarball %s", zip_path, tar_path)
    with zipfile.ZipFile(zip_path) as _zip:
        with tarfile.open(tar_path, 'w:xz') as tar:
            for zip_info in _zip.infolist():
                tar_info = tarfile.TarInfo(name=zip_info.filename)
                tar_info.size = zip_info.file_size
                tar_info.mtime = time.mktime(zip_info.date_time + (0, 0, 0))
                if zip_info.is_dir():
                    tar_info.mode = 0o755
                    tar_info.type = tarfile.DIRTYPE
                else:
                    tar_info.mode = 0o644
                tar.addfile(
                    tarinfo=tar_info, fileobj=_zip.open(zip_info.filename)
                )


def extract_zipfile(zip_path, output_path):
    """Extract the zip file pointed by zip_path argument in directory pointed by
    output_path argument and return the path to the zip file subdirectory."""
    with zipfile.ZipFile(zip_path, "r") as _zip:
        # A function analogous to tar_safe_extractall() is not needed as
        # ZipFile.extractall() method is protected against absolute and backward
        # relative paths, and zip format does not support with file UID/GID.
        _zip.extractall(output_path)
        return output_path.joinpath(zip_subdir(_zip))


def extract_tarball(tar_path, output_path, strip=0):
    """Extract the tarball file pointed by tar_path argument in directory
    pointed by output_path argument and return the path to the tarball
    subdirectory."""
    with tarfile.open(tar_path) as tar:
        tar_safe_extractall(tar, output_path, strip)
        return output_path.joinpath(tar_subdir(tar))


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
