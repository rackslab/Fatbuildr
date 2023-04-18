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
import shutil

from .git import GitRepository, PatchesDir
from .utils import dl_file, verify_checksum, extract_artifact_sources_archives
from .protocols.wire import WireSourceArchive
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
        sources=[],
    ):
        self.apath = apath
        self.derivative = derivative
        self.artifact = artifact
        self.defs = defs
        self.user = user
        self.email = email
        self.git = None
        self.version = None
        self.sources = sources
        self.main_source = None
        self.supplementary_sources = []

    def _already_loaded_source(self, source):
        """Return True if the given source is already loaded in self.main_source
        or in self.supplementary_sources list, False otherwise."""
        if self.main_source is not None and self.main_source.id == source.id:
            return True
        for _source in self.supplementary_sources:
            if _source.id == source.id:
                return True
        return False

    def run(self, launch_subshell: bool = True):
        logger.debug("Running patch queue for artifact %s", self.artifact)

        # If sources archives has been generated, use them directly.
        for source in self.sources:
            if source.is_main(self.artifact):
                self.main_source = source
                # extract version from tarball name (with .tar.xz extension)
                self.version = source.path.name[len(self.artifact) + 1 : -7]
            else:
                self.supplementary_sources.append(source)
        # Download other sources archives defined in artifact definition
        for source in self.defs.sources:
            # skip already loaded source
            if self._already_loaded_source(source):
                continue
            if source.id == self.artifact:
                self.main_source = WireSourceArchive(
                    source.id, self._dl_tarball(source)
                )
                # extract version from artifact definition
                self.version = source.version(self.derivative)
            else:
                self.supplementary_sources.append(
                    WireSourceArchive(source.id, self._dl_tarball(source))
                )

        # create tmp directory for the git repository
        tmpdir = Path(tempfile.mkdtemp(prefix=f"fatbuildr-pq-{self.artifact}"))
        CleanupRegistry.add_tmpdir(tmpdir)
        logger.debug("Created temporary directory %s", tmpdir)

        # Extract artifact source tree with all source archives
        repo_path = extract_artifact_sources_archives(
            tmpdir,
            self.artifact,
            self.main_source,
            self.supplementary_sources,
            with_symlinks=True,
        )

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
        logger.debug("Removing temporary directory %s", tmpdir)
        shutil.rmtree(tmpdir)
        CleanupRegistry.del_tmpdir(tmpdir)

    def _dl_tarball(self, source):
        """Download artifact tarball using the URL found in artifact definition
        metadata file, unless already present in cache, and verify its checksum.
        Return the path to the tarball in cache."""
        cache_dir = default_user_cache().expanduser()

        # create user local cache directory if not present
        if not cache_dir.exists():
            logger.debug("Creating user cache directory %s", cache_dir)
            cache_dir.mkdir()

        # define tarball path in user local cache
        tarball_path = cache_dir.joinpath(source.filename(self.derivative))

        # download and save tarball in user cache
        if not tarball_path.exists():
            dl_file(source.url(self.derivative), tarball_path)

        # verify all declared checksums for source
        for checksum in source.checksums(self.derivative):
            verify_checksum(
                tarball_path,
                checksum[0],
                checksum[1],
            )

        return tarball_path

    def _launch_subshell(self):
        # Launch subshell

        os.environ['FATBUILDR_PQ'] = self.artifact
        logger.info(
            "\n\nWelcome to Fatbuildr patch queue shell!\n"
            "\n"
            "  Artifact: %s\n"
            "  Derivative: %s\n"
            "  Version: %s\n"
            "\n"
            "Perform all the modifications in Git repository and exit the "
            "shell when you are done.\n",
            self.artifact,
            self.derivative,
            self.version,
        )
        subprocess.run(['/bin/bash'], cwd=self.git.path)
