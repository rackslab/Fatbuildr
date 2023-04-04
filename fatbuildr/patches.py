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

import tempfile
import subprocess
import os
from pathlib import Path
import tarfile
import shutil

from .git import GitRepository, PatchesDir
from .utils import dl_file, verify_checksum, extract_tarball
from .cleanup import CleanupRegistry
from .log import logr

logger = logr(__name__)


def default_user_cache():
    """Returns the default path to the user cache directory, through
    XDG_CACHE_HOME environment variable if it is set."""
    subdir = 'fatbuildr'
    xdg_env = os.getenv('XDG_CACHE_HOME')
    if xdg_env:
        return Path(xdg_env).joinpath(subdir)
    else:
        return Path(f"~/.local/{subdir}")


class PatchQueue:
    def __init__(
        self,
        apath,
        derivative,
        artifact,
        defs,
        user,
        email,
        version,
        src_tarball=None,
    ):
        self.apath = apath
        self.derivative = derivative
        self.artifact = artifact
        self.defs = defs
        self.user = user
        self.email = email
        self.version = version
        self.src_tarball = src_tarball
        self.git = None

    def run(self, launch_subshell: bool = True):
        logger.debug("Running patch queue for artifact %s", self.artifact)

        # If the tarball has been generated, use it directely. Otherwise,
        # download the tarball.
        if self.src_tarball:
            tarball_path = self.src_tarball
        else:
            tarball_path = self._dl_tarball()

        # create tmp directory for the git repository
        tmpdir = Path(tempfile.mkdtemp(prefix=f"fatbuildr-pq-{self.artifact}"))
        CleanupRegistry.add_tmpdir(tmpdir)
        logger.debug(f"Created temporary directory %s", tmpdir)

        # extract tarball in the tmp directory
        repo_path = extract_tarball(tarball_path, tmpdir)

        # init the git repository with its initial commit
        self.git = GitRepository(repo_path, self.user, self.email)

        # import existing patches in queue
        patches_dir = PatchesDir(self.apath, self.version)
        self.git.import_patches(patches_dir)

        if launch_subshell:
            # launch subshell and wait user to exit
            self._launch_subshell()

        # export patch queue
        self.git.export_queue(patches_dir)

        # remove temporary directory
        logger.debug(f"Removing temporary directory %s", tmpdir)
        shutil.rmtree(tmpdir)
        CleanupRegistry.del_tmpdir(tmpdir)

    def _dl_tarball(self):
        """Download artifact tarball using the URL found in artifact definition
        metadata file, unless already present in cache, and verify its checksum.
        Return the path to the tarball in cache."""
        tarball_url = self.defs.tarball_url(self.version)

        cache_dir = default_user_cache().expanduser()

        # create user local cache directory if not present
        if not cache_dir.exists():
            logger.debug("Creating user cache directory %s", cache_dir)
            cache_dir.mkdir()

        # define tarball path in user local cache
        tarball_path = cache_dir.joinpath(
            self.defs.tarball_filename(self.version)
        )

        # download and save tarball in user cache
        if not tarball_path.exists():
            dl_file(tarball_url, tarball_path)

        # verify checksum of tarball
        verify_checksum(
            tarball_path,
            self.defs.checksum_format(self.derivative),
            self.defs.checksum_value(self.derivative),
        )

        return tarball_path

    def _launch_subshell(self):
        # Launch subshell

        os.environ['FATBUILDR_PQ'] = self.artifact
        logger.info(
            "\n\nWelcome to Fatbuildr patch queue shell!\n"
            "\n"
            f"  Artifact: {self.artifact}\n"
            f"  Derivative: {self.derivative}\n"
            f"  Version: {self.version}\n"
            "\n"
            "Perform all the modifications in Git repository and exit the shell when you are done.\n"
        )
        subprocess.run(['/bin/bash'], cwd=self.git.path)
