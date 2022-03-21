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

from .git import GitRepository
from .utils import dl_file, verify_checksum, tar_subdir
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
        basedir,
        subdir,
        derivative,
        artefact,
        defs,
        user,
        email,
    ):
        self.basedir = basedir
        self.subdir = subdir
        self.derivative = derivative
        self.artefact = artefact
        self.defs = defs
        self.user = user
        self.email = email
        self.version = self.defs.version(self.derivative)
        self.git = None

    def run(self):
        logger.debug("Running patch queue for artefact %s", self.artefact)

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

        # create tmp directory for the git repository
        tmpdir = Path(tempfile.mkdtemp(prefix=f"fatbuildr-pq-{self.artefact}"))
        CleanupRegistry.add_tmpdir(tmpdir)
        logger.debug(f"Created temporary directory %s", tmpdir)

        # extract tarball in the tmp directory
        with tarfile.open(tarball_path, 'r') as tar:
            tar.extractall(path=tmpdir)
            repo_path = tmpdir.joinpath(tar_subdir(tar))

        # init the git repository with its initial commit
        self.git = GitRepository(repo_path, self.user, self.email)

        # import existing patches in queue
        patches_dir = Path(self.basedir, self.subdir, 'patches')
        self.git.import_patches(patches_dir)

        # launch subshell and wait user to exit
        self._launch_subshell()

        # export patch queue
        self.git.export_queue(patches_dir)

    def _launch_subshell(self):
        # Launch subshell

        os.environ['FATBUILDR_PQ'] = self.artefact
        logger.info(
            "\n\nWelcome to Fatbuildr patch queue shell!\n"
            "\n"
            f"  Artefact: {self.artefact}\n"
            f"  Derivative: {self.derivative}\n"
            f"  Version: {self.version}\n"
            "\n"
            "Perform all the modifications in Git repository and exit the shell when you are done.\n"
        )
        subprocess.run(['/bin/bash'], cwd=self.git.path)
