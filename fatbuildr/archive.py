#!/usr/bin/env python3
#
# Copyright (C) 2023 Rackslab
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

import tarfile
import zipfile
import time
import mimetypes
import os
import shutil
import copy

from .utils import sanitized_stem
from .log import logr

logger = logr(__name__)


def is_zip(path):
    """True if the archive is a zip file, False otherwise."""
    return mimetypes.guess_type(str(path))[0] == 'application/zip'


class BaseArchiveFile:
    def __init__(self, path):
        self.path = path


class ArchiveFileZip(BaseArchiveFile):
    def __init__(self, path):
        super().__init__(path)
        self.is_zip = True

    @property
    def stem(self):
        return self.path.stem

    def subdir(self, fh=None):
        """Returns the name of the subdirectory at the root of the zip file, or
        raise RuntimeError if not found. The fh argument can either be an opened
        zipfile.ZipFile object or None. For the latter, the zip file is opened
        with a recursive call."""
        if fh is None:
            with zipfile.ZipFile(self.path) as fh:
                return self.subdir(fh)
        for member in fh.infolist():
            if '/' not in member.filename[:-1]:
                subdir = member
                break
        if not subdir.is_dir():
            raise RuntimeError(
                f"unable to define zip file {self.path.name} subdirectory"
            )
        return subdir.filename[:-1]

    @property
    def has_single_toplevel(self):
        """True if the archive has a single element at its top-level, False
        otherwise."""
        already_found = False
        with zipfile.ZipFile(self.path) as fh:
            for member in fh.infolist():
                if '/' not in member.filename[:-1]:
                    if already_found:
                        return False
                    already_found = True
        return True

    @staticmethod
    def extractall(fh, output_path, strip):
        """Extract all members from the zip archive to the directory pointed by
        output_path. This function is largely a copy of Python standard library
        ZipFile._extract_member() except stripping support. The strip argument
        can be used with a value above 0 to remove the first n elements of
        members path. The zip archive members with paths below this level are
        skipped with an info message."""
        for member in fh.infolist():
            # interpret absolute pathname as relative, remove drive letter or
            # UNC path, redundant separators, "." and ".." components.
            arcname = os.path.splitdrive(member.filename)[1]
            invalid_path_parts = ('', os.path.curdir, os.path.pardir)
            arcname = os.path.sep.join(
                x
                for x in arcname.split(os.path.sep)
                if x not in invalid_path_parts
            )

            if strip:
                if arcname.count('/') < strip:
                    logger.info(
                        "skipping extraction of file %s due to stripping",
                        arcname,
                    )
                    continue
                extracted_path = output_path.joinpath(
                    arcname.split('/', strip)[-1]
                )
            else:
                extracted_path = output_path.joinpath(arcname)

            if member.is_dir():
                if not extracted_path.is_dir():
                    extracted_path.mkdir()
                continue

            with fh.open(member) as source, open(
                extracted_path, "wb"
            ) as target:
                shutil.copyfileobj(source, target)

    def extract(self, output_path, strip):
        """Extract the zip file pointed by zip_path argument in directory
        pointed by output_path argument and return the path to the zip file
        subdirectory."""
        with zipfile.ZipFile(self.path) as fh:
            ArchiveFileZip.extractall(fh, output_path, strip)
            return output_path.joinpath(self.subdir(fh=fh))


class ArchiveFileTar(BaseArchiveFile):
    def __init__(self, path):
        super().__init__(path)
        self.is_zip = False

    @property
    def stem(self):
        return self.path.name.rsplit('.', 2)[0]

    def subdir(self, fh=None):
        """Returns the name of the subdirectory at the root of the tarball, or
        raise RuntimeError if not found. The fh argument can either
        be an opened tarfile.TarFile object or None. For the latter, the tarball
        is opened with a recursive call."""
        if fh is None:
            with tarfile.open(self.path) as fh:
                return self.subdir(fh)
        # search for first member found in root of archive (w/o '/' in name)
        for member in fh.getmembers():
            if '/' not in member.name:
                subdir = member
                break
        if not subdir.isdir():
            raise RuntimeError(
                f"unable to define tarball {self.path.name} subdirectory"
            )
        return subdir.name

    @property
    def has_single_toplevel(self):
        """True if the archive has a single element at its top-level, False
        otherwise."""
        already_found = False
        with tarfile.open(self.path) as fh:
            for member in fh.getmembers():
                if '/' not in member.name:
                    if already_found:
                        return False
                    already_found = True
        return True

    @staticmethod
    def tar_safe_extractall(fh, output_path, strip):
        """Extract all members from the archive tar to the directory pointed by
        path. This function is largely a copy of Python standard library
        TarFile.extractall() except:
        - It checks for and skips with warning members with absolute path or
        with parent relative directory (ie '..')
        - It does not set attributes (mode, time) of directory pointed by path
        in respect with archive content for root directory. If path already
        exists, its attributes are unmodified. If path does not already exist,
        its mode is set with default mode (ie. in respect to current umask).
        The strip argument can be used with a value above 0 to remove the first
        n elements of members path. The tarball members with paths below this
        level are skipped with an info message.
        - Stripping support. The strip argument can be used with a value above 0
        to remove the first n elements of members path. The tarball archive
        members with paths below this level are skipped with an info message."""
        directories = []

        for tarinfo in fh:
            # Detect and skip with warning unsafe members
            if tarinfo.name.startswith('/') or '..' in tarinfo.name:
                logger.warning(
                    "skipping extraction of unsafe file %s from archive %s",
                    tarinfo.name,
                    fh.name,
                )
                continue
            if strip:
                if tarinfo.name.count('/') < strip:
                    logger.info(
                        "skipping extraction of file %s due to stripping",
                        tarinfo.name,
                    )
                    continue
                extracted_path = output_path.joinpath(
                    tarinfo.name.split('/', strip)[-1]
                )
            else:
                extracted_path = output_path.joinpath(tarinfo.name)
            if tarinfo.isdir() and tarinfo.name != '.':
                # Extract directories with a safe mode, except for '.'.
                directories.append((tarinfo, extracted_path))
                tarinfo = copy.copy(tarinfo)
                tarinfo.mode = 0o700
            # Do not set_attrs directories, as we will do that further down.
            # TarFile._extract_member() hidden method is used instead of
            # TarFile.extract() because we need to control the path of the
            # extracted file.
            fh._extract_member(
                tarinfo, str(extracted_path), set_attrs=not tarinfo.isdir()
            )

        # Reverse sort directories.
        directories.sort(key=lambda a: a[1])
        directories.reverse()

        # Set correct owner, mtime and filemode on directories (except on '.')
        for tarinfo, extracted_path in directories:
            fh.chown(tarinfo, extracted_path, numeric_owner=False)
            fh.utime(tarinfo, extracted_path)
            fh.chmod(tarinfo, extracted_path)

    def extract(self, output_path, strip):
        """Extract the tarball file pointed by tar_path argument in directory
        pointed by output_path argument and return the path to the tarball
        subdirectory."""
        with tarfile.open(self.path) as fh:
            ArchiveFileTar.tar_safe_extractall(fh, output_path, strip)
            return output_path.joinpath(self.subdir(fh=fh))


class ArchiveFile:
    def __init__(self, path):
        self.path = path
        if is_zip(path):
            self._archive = ArchiveFileZip(path)
        else:
            self._archive = ArchiveFileTar(path)

    @property
    def has_single_toplevel(self):
        return self._archive.has_single_toplevel

    @property
    def is_zip(self):
        return self._archive.is_zip

    @property
    def stem(self):
        return self._archive.stem

    @property
    def sanitized_stem(self):
        return sanitized_stem(self._archive.stem)

    @property
    def subdir(self):
        return self._archive.subdir()

    def extract(self, output, strip=0):
        return self._archive.extract(output, strip)

    def convert_tar(self, new_path):
        """Convert the given zip file to a tarball with xz compression. The zip
        file metadata (size/mtime) are preserved so the generated files are
        binary reproducible."""
        logger.info("Converting zip file %s to tarball %s", self.path, new_path)
        assert self._archive.is_zip
        with zipfile.ZipFile(self._archive.path) as zip:
            with tarfile.open(new_path, 'w:xz') as tar:
                for zip_info in zip.infolist():
                    tar_info = tarfile.TarInfo(name=zip_info.filename)
                    tar_info.size = zip_info.file_size
                    tar_info.mtime = time.mktime(zip_info.date_time + (0, 0, 0))
                    if zip_info.is_dir():
                        tar_info.mode = 0o755
                        tar_info.type = tarfile.DIRTYPE
                    else:
                        tar_info.mode = 0o644
                    tar.addfile(
                        tarinfo=tar_info, fileobj=zip.open(zip_info.filename)
                    )
        self.path = new_path
        self._archive = ArchiveFileTar(new_path)


class SourceArchive(ArchiveFile):
    def __init__(self, id, path):
        super().__init__(path)
        self.id = id

    def is_main(self, artifact):
        """Returns True if this archive is the main archive of the given
        artifact."""
        return self.id == artifact
