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
import shutil
import tarfile
import stat
from pathlib import Path
from datetime import date
from typing import List

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

from ..protocols.exports import (
    ExportableType,
    ExportableField,
    ExportableTaskField,
)

from ..tasks import RunnableTask
from ..cleanup import CleanupRegistry
from ..artifact import ArtifactDefsFactory
from ..registry.formats import ArtifactVersion
from ..archive import ArchiveFile, SourceArchive
from ..git import GitRepository, PatchesDir
from ..templates import Templeter
from ..utils import (
    dl_file,
    verify_checksum,
    extract_artifact_sources_archives,
    current_user,
    host_architecture,
)
from ..log import logr

logger = logr(__name__)


class ArtifactSourceArchive(ExportableType, SourceArchive):
    """Class to represent an artifact source archive."""

    EXFIELDS = {
        ExportableField('id'),
        ExportableField('path', Path),
    }


class ArtifactBuild(RunnableTask):
    """Generic parent class of all ArtifactBuild formats."""

    TASK_NAME = 'artifact build'
    EXFIELDS = {
        ExportableTaskField('format'),
        ExportableTaskField('distribution'),
        ExportableTaskField('architectures', List[str]),
        ExportableTaskField('archives', List[ArtifactSourceArchive]),
        ExportableTaskField('derivative'),
        ExportableTaskField('artifact'),
        ExportableTaskField('author'),
        ExportableTaskField('email'),
        ExportableTaskField('message'),
    }

    def __init__(
        self,
        task_id,
        user,
        place,
        instance,
        format,
        distribution,
        architectures,
        derivative,
        artifact,
        author,
        email,
        message,
        tarball,
        sources,
        interactive,
    ):
        super().__init__(
            task_id, user, place, instance, interactive=interactive
        )
        self.format = format
        self.distribution = distribution
        self.architectures = architectures
        self.derivative = derivative
        self.artifact = artifact
        self.author = author
        self.email = email
        self.message = message
        self.input_tarball = ArchiveFile(Path(tarball))
        self.sources = sources
        self.cache = self.instance.cache.artifact(self)
        self.registry = self.instance.registry_mgr.factory(self.format)
        # Get the recursive list of derivatives extended by the given
        # derivative.
        self.derivatives = self.instance.pipelines.recursive_derivatives(
            self.derivative
        )
        self.image = self.instance.images_mgr.image(self.format)
        self.defs = None  # loaded in prepare()
        self.version = None  # initialized in prepare(), after defs are loaded
        # The source upstream archives, initialized in prepare(), after optional
        # pre-script is processed.
        self.archives = list()
        # Initialized in prepare(), as it requires the version to be known.
        self.patches_dir = None

    def __getattr__(self, name):
        # try in defs
        try:
            return getattr(self.defs, name)
        except AttributeError:
            raise AttributeError(
                f"{self.__class__.__name__} does not have {name} attribute"
            )

    def archive(self, searched_id):
        """Returns the ArtifactSourceArchive with the given archive ID or None
        if not found."""
        for archive in self.archives:
            if archive.id == searched_id:
                return archive
        return None

    @property
    def main_archive(self):
        """Returns the main ArtifactSourceArchive for this artifact or None if
        not found."""
        return self.archive(self.artifact)

    @property
    def other_archives(self):
        """Returns the list of all artifact source archives except the main
        archive."""
        return [
            archive
            for archive in self.archives
            if not archive.is_main(self.artifact)
        ]

    def archive_in_build_place(self, archive):
        """Returns True if the artifact source archive is located in build place
        (ie. the archive was provided by the user within the build request), or
        False otherwise.
        This code does not call archive.is_relative_to(self.place) method
        because Fatbuildr supports Python 3.6+ and this method is only available
        starting from Python 3.9.
        """
        try:
            archive.path.relative_to(self.place)
            return True
        except ValueError:
            return False

    def patch_selected(self, patch):
        """Check in the patch metadata in deb822 format if is it restricted to
        specific distributions or formats and in this case, check if it can be
        selected for the current build."""
        if 'Formats' in patch.meta and not patch.in_field(
            'Formats', self.format
        ):
            logger.info(
                "Skipping patch %s because it is restricted to other formats "
                "'%s'",
                patch.fullname,
                patch.meta['Formats'],
            )
            return False
        if 'Distributions' in patch.meta and not patch.in_field(
            'Distributions', self.distribution
        ):
            logger.info(
                "Skipping patch %s because it is restricted to other "
                "distributions '%s'",
                patch.fullname,
                patch.meta['Distributions'],
            )
            return False
        return True

    @cached_property
    def patches(self):
        """Returns the list of selected PatchFile found in artifact patches
        subdirectories."""
        patches = []
        for patches_subdir in self.patches_dir.subdirs:
            # skip subdir if it does not exists
            if not patches_subdir.exists():
                continue
            patches += [
                item
                for item in patches_subdir.patches
                if self.patch_selected(item)
            ]
        return patches

    def run(self):
        logger.info("Running build %s", self.id)
        self.prepare()
        self.build()
        self.registry.publish(self)

    def prepare(self):
        """Extract input tarball and, if not present in cache, download the
        package upstream source archives and verify their checksums."""

        # Extract artifact tarball in build place
        logger.info(
            "Extracting tarball %s in destination %s",
            self.input_tarball.path,
            self.place,
        )
        self.input_tarball.extract(self.place)

        # Remove the input tarball
        self.input_tarball.path.unlink()

        # ensure artifact cache directory exists
        self.cache.ensure()

        # load defs
        self.defs = ArtifactDefsFactory.get(
            self.place, self.artifact, self.format
        )

        if not len(self.sources) and not self.defs.main_source.has_source:
            # This artifact is not defined with an upstream source archive URL
            # and the user did not provide source archive within the build
            # request. This case happens for OSI format for example. The only
            # thing to do here is defining the targeted version.
            self.version = ArtifactVersion(
                self.defs.fullversion(self.derivative)
            )
            return

        # If source archives have been provided with the build request, use
        # them.
        for source in self.sources:
            source_archive_target = self.place.joinpath(source.path.name)
            logger.info(
                "Using provided source archive %s", source_archive_target
            )
            # Move the source archive in build place. The shutil module is
            # used here to support file move between different filesystems.
            # Unfortunately, PurePath.rename() does not support this case.
            shutil.move(source.path, source_archive_target)
            if source.is_main(self.artifact):
                # The main version of the artifact is extracted from the
                # main source archive name, it is prefixed by artifact name
                # followed by underscore, it is suffixed by the extension
                # '.tar.xz'.
                main_version_str = source.path.name[len(self.artifact) + 1 : -7]
                logger.debug(
                    "Artifact main version extracted from source tarball name: %s",
                    main_version_str,
                )
                self.version = ArtifactVersion(
                    f"{main_version_str}-{self.defs.release}"
                )
            self.archives.append(
                ArtifactSourceArchive(source.id, source_archive_target)
            )

        # If the artifact version has not been defined base on source archive
        # provided in the build request, define the version based on artifact
        # definition
        if self.version is None:
            self.version = ArtifactVersion(
                self.defs.fullversion(self.derivative)
            )

        # If the source archive has not been provided and the artifact is
        # defined with sources archives URLs, they are downloaded in cache
        # (if not already present) using these URLs.
        for source in self.defs.sources:
            # Skip archives whose source have already been provided in build
            # request.
            if self.archive(source.id) is not None:
                continue

            if not self.cache.has_archive(source.id):
                dl_file(
                    self.defs.source(source.id).url(self.derivative),
                    self.cache.archive(source.id),
                )

            # verify all declared checksums for source
            for checksum in source.checksums(self.derivative):
                verify_checksum(
                    self.cache.archive(source.id),
                    checksum[0],
                    checksum[1],
                )

            logger.info(
                "Using artifact source archive from cache %s",
                self.cache.archive(source.id),
            )
            self.archives.append(
                ArtifactSourceArchive(source.id, self.cache.archive(source.id))
            )

        # Define patches_dir attribute now that version is well known
        self.patches_dir = PatchesDir(self.place, self.version.main)

        if len(self.other_archives):
            self.other_archives_symlinks_patch()

        # run prescript if present
        self.prescript()

        # Render rename index template if present
        rename_idx_path = self.place.joinpath('rename')
        rename_idx_tpl_path = rename_idx_path.with_suffix('.j2')
        if rename_idx_tpl_path.exists():
            logger.info(
                "Rendering rename index template %s", rename_idx_tpl_path
            )
            with open(rename_idx_path, 'w+') as fh:
                fh.write(
                    Templeter().frender(
                        rename_idx_tpl_path, version=self.version
                    )
                )

        # Follow rename index rules if present
        if rename_idx_path.exists():
            with open(rename_idx_path) as fh:
                for line in fh:
                    line = line.strip()
                    if not len(line):
                        continue  # skip empty line
                    try:
                        (src, dest) = line.split(' ')
                    except ValueError:
                        logger.warning(
                            "Unable to parse rename index rule '%s'", line
                        )
                        continue
                    src_path = self.place.joinpath(src)
                    dest_path = self.place.joinpath(dest)
                    if not src_path.exists():
                        logger.warning(
                            "Source file %s in rename index not found", src_path
                        )
                        continue
                    logger.info("Renaming %s → %s", src_path, dest_path)
                    src_path.rename(dest_path)

        # Render all templates found in format subdirectory
        for tpl_path in sorted(self.place.joinpath(self.format).rglob("*.j2")):
            dest_path = tpl_path.with_suffix('')
            logger.info(
                "Rendering file %s based on template %s", dest_path, tpl_path
            )
            with open(dest_path, 'w+') as fh:
                fh.write(Templeter().frender(tpl_path, version=self.version))
                # Preserve template file mode on rendered file
                dest_path.chmod(tpl_path.stat().st_mode)

    def other_archives_symlinks_patch(self):
        """Create patch to add symlink from generic supplementary artifact
        source name to the subdirectory named after the source archive
        filename."""
        # Create temporary upstream directory
        upstream_dir = self.place.joinpath('upstream')
        upstream_dir.mkdir()

        archive_subdir = extract_artifact_sources_archives(
            upstream_dir, self.artifact, self.main_archive, self.other_archives
        )

        # Remove .gitignore file if present, to avoid modification realized
        # by pre script being ignored when generating the resulting patch.
        gitignore_path = archive_subdir.joinpath('.gitignore')
        if gitignore_path.exists():
            logger.info("Removing .gitignore from upstream archive")
            gitignore_path.unlink()

        # init the git repository with its initial commit
        git = GitRepository(archive_subdir, self.author, self.email)

        # import existing patches in queue
        if not self.patches_dir.empty:
            git.import_patches(self.patches_dir)

        for archive in self.other_archives:
            logger.debug(
                "Creating symlink supplementary source directory %s → %s",
                archive.id,
                archive.stem,
            )
            archive_subdir.joinpath(archive.id).symlink_to(
                archive.sanitized_stem
            )
        # Export patch with symlinks in patch queue
        git.commit_export(
            self.patches_dir.version_subdir,
            9998,
            'fatbuildr-supplementary-sources-symlinks',
            self.author,
            self.email,
            "Patch generated by fatbuildr to symlink artifact "
            "supplementary source archives subdirectories",
            files=[archive.id for archive in self.other_archives],
        )

        # Make sure user can remove all files by ensuring it has write
        # permission on all directories recursively. This is notably required
        # with go modules that are installed without write permissions to avoid
        # unwanted modifications.
        def rchmod(path):
            for child in path.iterdir():
                if child.is_dir():
                    child.chmod(child.stat().st_mode | stat.S_IWUSR)
                    rchmod(child)

        logger.debug(
            "Ensuring write permissions in upstream directory recursively "
            "prior to removal"
        )
        rchmod(upstream_dir)

        logger.debug(
            "Removing temporary upstream directory used for generating "
            "symlinks to other sources"
        )
        # Remove temporary upstream directory
        shutil.rmtree(upstream_dir)

    def prescript(self):
        """Run the prescript"""
        # Prescript cannot run without build environment, it is handled at
        # ArtifactEnvBuild level.
        pass

    def cruncmd(self, cmd, **kwargs):
        """Run command in container and log output in build log file."""
        _binds = [self.place, self.cache.dir]
        # Before the first artifact is actually published, the registry does
        # not exist. Then check it really exists, then bind-mount it.
        if self.registry.exists:
            _binds.append(self.registry.path)
        super().cruncmd(self.image, cmd, init=False, binds=_binds, **kwargs)


class ArtifactEnvBuild(ArtifactBuild):
    """Abstract class for artifact builds using a build environments in
    container images (eg. deb, rpm)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get the build environment name corresponding to the distribution
        self.env_name = self.instance.pipelines.dist_env(self.distribution)
        # Initialized in prescript_supp_tarball()
        self.prescript_tarballs = list()
        logger.debug(
            "Build environment selected for distribution %s: %s",
            self.distribution,
            self.env_name,
        )

    @cached_property
    def native_env(self):
        """Returns the BuildEnv considering the artifact build format and
        environment name for the host native architecture."""
        return self.instance.images_mgr.build_env(
            self.format, self.env_name, host_architecture()
        )

    @property
    def build_keyring(self):
        """If not already present, export instance keyring public key with
        armored format in task directory and return its path."""
        path = self.place.joinpath('keyring.asc')
        if not path.exists():
            with open(path, 'w+') as fh:
                fh.write(self.instance.keyring.export())
        return path

    @property
    def prescript_path(self):
        """Returns path to the artifact prescript, which may not exist."""
        return self.place.joinpath('pre.sh')

    @property
    def prewrapper_path(self):
        """Returns path to the prescript wrapper script."""
        return self.image.common_libdir.joinpath('pre-wrapper.sh')

    def prescript_token(self, token):
        """Returns the list of values found for the given token parameter in the
        prescript. If the prescript is absent or if the parameter is not found,
        an empty list is returned."""
        in_file = []

        # Check the prescript is present or return an empty list
        if not self.prescript_path.exists():
            return in_file

        with open(self.prescript_path, "r") as fh:
            for line in fh:
                if line.startswith(f"#PRESCRIPT_{token}"):
                    try:
                        line = line.strip()  # Remove trailing EOL
                        in_file = line.split(' ')[1:]
                        break
                    except IndexError:
                        logger.warn(
                            "Unable to parse prescript %s line %s",
                            token,
                            line,
                        )
        if not len(in_file):
            logger.debug("Prescript in-file %s not found", token)
        return in_file

    @cached_property
    def prescript_deps(self):
        """Returns the concatenation of the list of basic prescript dependencies
        declared in configuration file for the image and the optional list of
        dependencies found in prescript."""
        in_file = self.prescript_token('DEPS')
        return list(set(self.image.prescript_deps + in_file))

    @cached_property
    def defined_prescript_tarballs(self):
        """Returns the list of subfolders generated in prescripts to include in
        supplementary tarballs."""
        return self.prescript_token('TARBALLS')

    def prescript_in_env(self, tarball_subdir):
        """Method to run the prescript in build environment. This method must
        be implemented at format specialized classes level."""
        raise NotImplementedError

    def prescript_supp_tarball(self, tarball_subdir):
        """Generate the prescript supplementary tarballs and fills
        self.prescript_tarballs list attribute."""
        for subdir in self.defined_prescript_tarballs:
            logger.info(
                "Generating supplementary tarball %s",
                self.supp_tarball_path(subdir),
            )
            with tarfile.open(self.supp_tarball_path(subdir), 'x:xz') as tar:
                renamed = tarball_subdir.joinpath(
                    self.prescript_supp_subdir_renamed(subdir)
                )
                tar.add(
                    renamed,
                    arcname=renamed.name,
                    recursive=True,
                )
            self.prescript_tarballs.append(
                ArtifactSourceArchive(subdir, self.supp_tarball_path(subdir))
            )

    def prescript_supp_subdir_renamed(self, subdir):
        """Returns the name (string format) to uniquely timestamped renamed
        supplementary tarball subdirectory."""
        return f"{subdir}-{date.today().strftime('%Y%m%d')}-{self.id[:8]}"

    def prescript(self):
        """Run the prescript."""

        # Check the prescript is present or leave
        if not self.prescript_path.exists():
            logger.debug(
                "Prescript not found, continuing with unmodified artifact "
                "sources"
            )
            return

        logger.info("Running the prescript")

        # Create temporary upstream directory
        upstream_dir = self.place.joinpath('upstream')
        upstream_dir.mkdir()

        archive_subdir = extract_artifact_sources_archives(
            upstream_dir, self.artifact, self.main_archive, self.other_archives
        )

        # Remove .gitignore file if present, to avoid modification realized
        # by pre script being ignored when generating the resulting patch.
        gitignore_path = archive_subdir.joinpath('.gitignore')
        if gitignore_path.exists():
            logger.info("Removing .gitignore from upstream archive")
            gitignore_path.unlink()

        # init the git repository with its initial commit
        git = GitRepository(archive_subdir, self.author, self.email)

        # import existing patches in queue
        if not self.patches_dir.empty:
            git.import_patches(self.patches_dir)

        # Now run the prescript!
        self.prescript_in_env(archive_subdir)

        if len(self.defined_prescript_tarballs):
            # Rename and symlink prescript tarballs subdirectories with unique
            # timestamped names, so the resulting supplementary tarball name is
            # also unique and cannot conflict in targeted package repository
            # with another existing supplementary tarball with different
            # content.
            for subdir in self.defined_prescript_tarballs:
                subdir_path = archive_subdir.joinpath(subdir)
                target = archive_subdir.joinpath(
                    self.prescript_supp_subdir_renamed(subdir)
                )
                logger.debug(
                    "Renaming supplementary tarball subdir %s → %s",
                    subdir,
                    target,
                )
                subdir_path.rename(target)
                # Create symbolic link for generic subdir to unique timestamped
                # subdirectory, using the target name to get a relative path.
                subdir_path.symlink_to(target.name)
            # Generate supplementary tarballs
            self.prescript_supp_tarball(archive_subdir)
            # Export patch with symlinks in patch queue
            git.commit_export(
                self.patches_dir.version_subdir,
                9999,
                'fatbuildr-prescript-symlinks',
                self.author,
                self.email,
                "Patch generated by fatbuildr to symlink prescript "
                "supplementary tarballs subdirectories",
                files=self.defined_prescript_tarballs,
            )
        else:
            # Export git repo diff in patch queue
            git.commit_export(
                self.patches_dir.version_subdir,
                9999,
                'fatbuildr-prescript',
                self.author,
                self.email,
                "Patch generated by artifact pre-script.",
                files=None,
            )

        # Make sure user can remove all files by ensuring it has write
        # permission on all directories recursively. This is notably required
        # with go modules that are installed without write permissions to avoid
        # unwanted modifications.
        def rchmod(path):
            for child in path.iterdir():
                if child.is_dir():
                    child.chmod(child.stat().st_mode | stat.S_IWUSR)
                    rchmod(child)

        logger.debug(
            "Ensuring write permissions in upstream directory recursively prior "
            "to removal"
        )
        rchmod(upstream_dir)

        logger.debug("Removing temporary upstream directory used for prescript")
        # Remove temporary upstream directory
        shutil.rmtree(upstream_dir)
