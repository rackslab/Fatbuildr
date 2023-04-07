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

import requests

from .log import logr
from .errors import FatbuildrRuntimeError

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


def extract_artifact_sources_archives(
    output_dir,
    artifact,
    main_archive,
    other_archives,
    prescript_archives=[],
    with_symlinks=False,
):

    # Extract main source archive in build place
    logger.debug(
        "Extracting main source archive %s in %s",
        main_archive.path,
        output_dir,
    )
    main_subdir = main_archive.extract(output_dir, strip=0)

    # Extract other sources archives in main archive subdir
    for archive in other_archives:
        assert not archive.is_main(artifact)
        target = main_subdir.joinpath(archive.sanitized_stem)
        logger.debug(
            "Extracting other source archive %s in %s",
            archive.path,
            target,
        )
        target.mkdir()
        if with_symlinks:
            main_subdir.joinpath(archive.id).symlink_to(archive.sanitized_stem)
        # Mimic dpkg-source behaviour by stripping the top-level directory
        # when the archive has a single top-level item. If the archive
        # contains several top-level files or directories, they are
        # extracted without stripping.
        if archive.has_single_toplevel:
            strip = 1
        else:
            strip = 0
        archive.extract(target, strip=strip)

    # Extract prescript archives in main archive subdir
    for archive in prescript_archives:
        target = main_subdir.joinpath(archive.subdir)
        logger.debug(
            "Extracting prescript archive %s in %s",
            archive.path,
            target,
        )
        target.mkdir()
        if archive.has_single_toplevel:
            strip = 1
        else:
            strip = 0
        archive.extract(target, strip=strip)

    return main_subdir


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
