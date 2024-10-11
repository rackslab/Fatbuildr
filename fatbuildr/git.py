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
import re
from datetime import datetime
from pathlib import Path

try:
    from functools import cached_property
except ImportError:
    # For Python 3.[6-7] compatibility. The dependency to cached_property
    # external library is not declared in setup.py, it is added explicitely in
    # packages codes only for distributions stuck with these old versions of
    # Python.
    #
    # This try/except block can be removed when support of Python < 3.8 is
    # dropped in Fatbuildr.
    from cached_property import cached_property


import pygit2
from debian import deb822

from .templates import Templeter
from .log import logr

logger = logr(__name__)


def parse_commit_meta(commit):
    return deb822.Deb822(commit.message.split("\n", 2)[2])


def is_meta_generic(meta):
    """Returns True if the patch metadata indicates a generic (ie. not version
    specific) patch, or False otherwise."""
    return 'Generic' in meta and meta['Generic'] == 'yes'


def load_git_repository(path: str):
    return pygit2.Repository(path)

class PatchesDir:
    """Class to manipulate patches directories and their subdirs. In pathlib
    classes the attributes are given as arguments to the constructor, and not to
    the __init__() method. This class overrides the constructor to add the
    version argument."""

    def __init__(self, path, version):
        self._path = Path(path.joinpath('patches'))
        self.version = version

    @cached_property
    def generic_subdir(self):
        return PatchesSubdir(self, 'generic')

    @cached_property
    def version_subdir(self):
        return PatchesSubdir(self, self.version)

    @property
    def subdirs(self):
        return (self.generic_subdir, self.version_subdir)

    @property
    def empty(self):
        """Returns True is either one subdirectory exists, False otherwise."""
        return (
            not self.generic_subdir.exists()
            and not self.version_subdir.exists()
        )

    def ensure(self):
        """Create patches directory if it does not exist yet."""
        if not self._path.exists():
            logger.debug("Creating artifact patches directory %s", self._path)
            self._path.mkdir()
            self._path.chmod(0o755)


class PatchesSubdir:
    """Class to manipulate patches subdirectories. In pathlib classes the
    attributes are given as arguments to the constructor, and not to the
    __init__() method. This class overrides the constructor to add the
    patches_dir argument."""

    def __init__(self, patches_dir, sub_dir):
        self.patches_dir = patches_dir
        self._path = self.patches_dir._path.joinpath(sub_dir)

    @property
    def patches(self):
        """Return sorted list of PatchFiles available in subdir."""
        return sorted([PatchFile(patch) for patch in self._path.iterdir()])

    def exists(self):
        return self._path.exists()

    def ensure(self):
        """Create patches subdirectory if it does not exist yet."""
        # First ensure parent patches directory
        self.patches_dir.ensure()

        if not self._path.exists():
            logger.debug("Creating patches subdirectory %s", self._path)
            self._path.mkdir()
            self._path.chmod(0o755)

    def clean(self):
        """Remove all existing patches in subdir."""
        if not self._path.exists():
            return
        for patch in self.patches:
            logger.debug("Removing old patch %s", patch.fullname)
            patch.remove()


class PatchFile:
    """Class to manipulate patch files."""

    TEMPLATE_KEY = 'Template'

    def __init__(self, path: Path):
        self._path = path

    def __lt__(self, other):
        return self._path < other._path

    @property
    def name(self):
        return self._path.name

    @property
    def fullname(self):
        return f"{self._path.parent.name}/{self._path.name}"

    @cached_property
    def content(self):
        with open(self._path, 'rb') as fh:
            return fh.read()

    @cached_property
    def title(self):
        # Extract commit title (1st line) from patch filename, by removing
        # the patch index before the first dash.
        return self._path.name.split('-', 1)[1]

    @cached_property
    def meta(self):
        return deb822.Deb822(self.content)

    @property
    def template(self):
        """Returns True if the patch is a template, ie. if it contains the
        template key in its metadata fields and False otherwise."""
        return (
            self.TEMPLATE_KEY in self.meta
            and self.meta[self.TEMPLATE_KEY] == 'yes'
        )

    def render(self, **kwargs):
        patch_tmp = self._path.with_suffix('.swp')
        self._path.rename(patch_tmp)
        logger.info("Rendering patch template %s", self._path)
        with open(self._path, 'w+') as fh:
            fh.write(
                Templeter().frender(patch_tmp, **kwargs)
            )
        patch_tmp.unlink()

    def in_field(self, field, value):
        """Returns True if value in found in space separated list field, or
        False otherwise."""
        return value in self.meta[field].split(' ')

    @property
    def generic(self):
        return self._path.parent.name == 'generic'

    @staticmethod
    def create(subdir, title):
        return PatchFile(subdir._path.joinpath(title))

    def write(self, meta, diff):
        with open(self._path, 'w+') as fh:
            fh.write(str(meta) + '\n\n')
            fh.write(diff)

    def rename(self, to):
        self._path.rename(to)

    def remove(self):
        self._path.unlink()


class GitRepository:
    def __init__(self, path, author, email, message_template=None):
        self.path = path

        # Remove .gitignore file if present, to avoid modification realized
        # by consumers being ignored when generating the resulting patch.
        gitignore_path = path.joinpath('.gitignore')
        if gitignore_path.exists():
            logger.info(
                "Removing .gitignore before initializing git repository %s",
                path,
            )
            gitignore_path.unlink()

        self._repo = pygit2.init_repository(path, bare=False)
        self._initial_commit(author, email)

        # Setup commit message template in git repository configuration if
        # defined and file exists.
        if message_template:
            if not message_template.exists():
                logger.warning(
                    "Unable to find git commit message template %s, ignoring",
                    message_template,
                )
            else:
                self._repo.config['commit.template'] = message_template

    def _initial_commit(self, author, email):
        ref = "HEAD"
        parents = []
        message = "Initial commit"
        self._base_commit(ref, parents, author, email, message)

    def _commit(self, author, email, title, meta, files):
        ref = self._repo.head.name
        parents = [self._repo.head.target]
        message = title + "\n\n" + str(meta)
        self._base_commit(ref, parents, author, email, message, files)

    def _base_commit(self, ref, parents, author, email, message, files=None):
        """Method actually performing the commit on ref, over the given parents
        with the given author, email and message. The files argument must either
        be None, or a list of files to index and commit. The paths must be
        relative to the root of the Git repository. If files is None (default),
        all modified files are selected for the commit."""
        index = self._repo.index
        if files is None:
            index.add_all()
        else:
            # add given files list to index
            for _file in files:
                index.add(_file)
        index.write()
        author_s = pygit2.Signature(author, email)
        committer_s = pygit2.Signature(author, email)
        tree = index.write_tree()
        self._repo.create_commit(
            ref, author_s, committer_s, message, tree, parents
        )

    def walker(self):
        """Returns an iterator over the commits in Git history."""
        return self._repo.walk(
            self._repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL
        )

    def diff(self, commit):
        """Returns the diff as a string between a commit and its first
        parent. When the diff is empty, None is returned."""
        return self._repo.diff(commit.parents[0], commit).patch

    def import_patches(self, patches_dir):
        """Import patches from all subdirs of patches_dir."""

        patches_subdirs = patches_dir.subdirs

        for patches_subdir in patches_subdirs:
            self._import_patches_subdir(patches_subdir)

    def _import_patches_subdir(self, patches_subdir):
        """Import patches in patches_subdir sorted by name into successive
        commits."""

        # If the patches directory does not exist, nothing to do here
        if not patches_subdir.exists():
            return

        for patch in patches_subdir.patches:
            self._apply_patch(patch)

    def _apply_patch(self, patch):

        # Parse metadata of the patch in deb822 format
        author_key = None
        # Search for accepted author key in metadata
        for key in ['Author', 'From']:
            if key in patch.meta:
                author_key = key
        # If an accepted author key has been found in meta, parse it. Otherwise
        # use default 'unknown' author
        if author_key:
            author_re = re.match(
                r'(?P<author>.+) <(?P<email>.+)>', patch.meta[author_key]
            )
            author = author_re.group('author')
            email = author_re.group('email')
            del patch.meta[author_key]
        else:
            author = 'Unknown Author'
            email = 'unknown@email.com'

        # If the patch is loaded from the generic subdir, add the corresponding
        # field in commit metadata
        if patch.generic:
            patch.meta['Generic'] = 'yes'

        # Apply the patch. The patch command is used because pygit2 does not
        # offer API to apply patches that allows not well formatted patch, with
        # fuzzing or offset.
        #
        # The --force argument prevents patch from asking questions
        # interactively.
        #
        # The backup and reject files are discarded as they do not add value
        # compared to git repository.
        cmd = [
            "patch",
            "--force",
            "--no-backup-if-mismatch",
            "--reject-file=-",
            "-p1",
        ]
        logger.info("Applying patch %s", patch.fullname)
        subprocess.run(cmd, input=patch.content, cwd=self.path)

        # Commit modifications
        self._commit(author, email, patch.title, patch.meta, files=None)

    def export_queue(self, patches_dir):
        """Export all commits in the repository into successive patches in
        patches_dir."""

        patches_dir.ensure()

        # Remove all existing patches
        for patches_subdir in patches_dir.subdirs:
            patches_subdir.clean()

        # Count generic and version specific commits
        index_generic = 0
        index_version = 0

        for commit in self.walker():
            if not commit.parents:
                break
            meta = parse_commit_meta(commit)
            if is_meta_generic(meta):
                index_generic += 1
            else:
                index_version += 1

        logger.debug(
            "Found %d generic and %s version specific commits in patch queue",
            index_generic,
            index_version,
        )

        # Export patches
        for commit in self.walker():
            if not commit.parents:
                break
            meta = parse_commit_meta(commit)
            if is_meta_generic(meta):
                self._export_commit(
                    patches_dir.generic_subdir, index_generic, commit, meta
                )
                index_generic -= 1
            else:
                self._export_commit(
                    patches_dir.version_subdir, index_version, commit, meta
                )
                index_version -= 1

    def _export_commit(self, patches_subdir, index, commit, meta):

        meta['Author'] = f"{commit.author.name} <{commit.author.email}>"

        # If the Generic field is present in commit metadata, remove it. The
        # patch is saved in generic subdirectory, this is how Fatbuildr knowns
        # the exported patch is generic.
        if 'Generic' in meta:
            del meta['Generic']

        patch_name = commit.message.split('\n')[0]
        patch_file = PatchFile.create(
            subdir=patches_subdir, title=f"{index:04}-{patch_name}"
        )

        logger.info(f"Generating patch file {patch_file.fullname}")

        diff = self.diff(commit)

        # Check if the diff is empty. When it is empty, just warn user, else
        # save patch in file.
        if diff:
            patches_subdir.ensure()
            patch_file.write(meta=meta, diff=diff)
        else:
            logger.warning("Patch diff is empty, skipping patch generation")

    def commit_export(
        self,
        patches_subdir,
        index,
        title,
        author,
        email,
        description,
        files,
    ):
        """Commit the modifications in the git repository and export these
        modifications into a patch file in patches_dir."""

        meta = deb822.Deb822()
        meta['Description'] = description
        meta['Forwarded'] = "no"
        meta['Last-Update'] = datetime.today().strftime('%Y-%m-%d')

        self._commit(author, email, title, meta, files)

        last_commit = self._repo[self._repo.head.target]

        meta = deb822.Deb822(last_commit.message.split("\n", 2)[2])
        self._export_commit(patches_subdir, index, last_commit, meta)
