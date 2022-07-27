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
from functools import cached_property

from ..protocols.exports import ExportableTaskField

from ..tasks import RunnableTask
from ..cleanup import CleanupRegistry
from ..artifact import ArtifactDefsFactory
from ..registry.formats import ArtifactVersion
from ..git import GitRepository, parse_patch
from ..templates import Templeter
from ..utils import (
    dl_file,
    verify_checksum,
    tar_subdir,
    tar_safe_extractall,
    current_user,
    host_architecture,
)
from ..log import logr

logger = logr(__name__)


class ArtifactBuild(RunnableTask):
    """Generic parent class of all ArtifactBuild formats."""

    TASK_NAME = 'artifact build'
    EXFIELDS = {
        ExportableTaskField('format'),
        ExportableTaskField('distribution'),
        ExportableTaskField('architectures', list[str]),
        ExportableTaskField('derivative'),
        ExportableTaskField('artifact'),
        ExportableTaskField('user'),
        ExportableTaskField('email'),
        ExportableTaskField('message'),
    }

    def __init__(
        self,
        task_id,
        place,
        instance,
        format,
        distribution,
        architectures,
        derivative,
        artifact,
        user_name,
        user_email,
        message,
        tarball,
        src_tarball,
        interactive,
    ):
        super().__init__(task_id, place, instance, interactive=interactive)
        self.format = format
        self.distribution = distribution
        self.architectures = architectures
        self.derivative = derivative
        self.artifact = artifact
        self.user = user_name
        self.email = user_email
        self.message = message
        self.input_tarball = Path(tarball)
        self.src_tarball = Path(src_tarball) if src_tarball else None
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
        # Path the upstream tarball, initialized in prepare(), after optional
        # pre-script is processed.
        self.tarball = None

    def __getattr__(self, name):
        # try in defs
        try:
            return getattr(self.defs, name)
        except AttributeError:
            raise AttributeError(
                f"{self.__class__.__name__} does not have {name} attribute"
            )

    @property
    def tarball_url(self):
        return self.defs.tarball_url(self.version.main)

    @property
    def tarball_filename(self):
        return self.defs.tarball_filename(self.version.main)

    @property
    def checksum_format(self):
        return self.defs.checksum_format(self.derivative)

    @property
    def checksum_value(self):
        return self.defs.checksum_value(self.derivative)

    def patch_selected(self, patch):
        """Check in the patch metadata in deb822 format if is it restricted to
        specific distributions or formats and in this case, check if it can be
        selected for the current build."""
        meta = parse_patch(patch)
        # check format
        if 'Formats' in meta and self.format not in meta['Formats'].split(' '):
            logger.info(
                "Skipping patch %s because it is restricted to other formats "
                "'%s'",
                patch,
                meta['Formats'],
            )
            return False
        # check distribution
        if 'Distributions' in meta and self.distribution not in meta[
            'Distributions'
        ].split(' '):
            logger.info(
                "Skipping patch %s because it is restricted to other "
                "distributions '%s'",
                patch,
                meta['Distributions'],
            )
            return False
        return True

    @property
    def patches_dir(self):
        """Returns the Path to the artifact patches directory."""
        return self.place.joinpath('patches')

    @property
    def patches(self):
        """Returns the sorted list of Path of patches found in artifact patches
        subdirectories."""
        patches = []
        patches_subdirs = (
            self.patches_dir.joinpath('generic'),
            self.patches_dir.joinpath(self.version.main),
        )
        for patches_subdir in patches_subdirs:
            # skip subdir if it does not exists
            if not patches_subdir.exists():
                continue
            patches += sorted(
                [
                    item
                    for item in patches_subdir.iterdir()
                    if self.patch_selected(item)
                ]
            )
        return patches

    @property
    def has_patches(self):
        """Returns True if at least one artifact patches subdirectory exists, or
        False otherwise."""
        return (
            self.patches_dir.joinpath('generic').exists()
            or self.patches_dir.joinpath(self.version.main).exists()
        )

    def run(self):
        logger.info("Running build %s", self.id)
        self.prepare()
        self.build()
        self.registry.publish(self)

    def prepare(self):
        """Extract input tarball and, if not present in cache, download the
        package upstream tarball and verify its checksum."""

        # Extract artifact tarball in build place
        logger.info(
            "Extracting tarball %s in destination %s",
            self.input_tarball,
            self.place,
        )
        with tarfile.open(self.input_tarball, 'r:xz') as tar:
            tar_safe_extractall(tar, self.place)

        # Remove the input tarball
        self.input_tarball.unlink()

        # ensure artifact cache directory exists
        self.cache.ensure()

        # load defs
        self.defs = ArtifactDefsFactory.get(
            self.place, self.artifact, self.format
        )

        if self.src_tarball:
            # If source tarball has been provided with the build request, use it.
            src_tarball_target = self.place.joinpath(self.src_tarball.name)
            logger.info("Using provided source tarball %s", src_tarball_target)
            # Move the source tarball in build place. The shutil module is used
            # here to support file move between different filesystems.
            # Unfortunately, PurePath.rename() does not support this case.
            shutil.move(self.src_tarball, src_tarball_target)

            # The main version of the artifact is extracted from the the source
            # tarball name, it is prefixed by artifact name followed by
            # underscore, it is suffixed by the extension'.tar.xz'.
            main_version_str = self.src_tarball.name[
                len(self.artifact) + 1 : -7
            ]
            logger.debug(
                "Artifact main version extracted from source tarball name: %s",
                main_version_str,
            )
            self.version = ArtifactVersion(
                f"{main_version_str}-{self.defs.release}"
            )
            self.tarball = src_tarball_target
        elif not self.defs.has_tarball:
            # This artifact is not defined with an upstream tarball URL and the
            # user did not provide source tarball within the build request. This
            # case happens for OSI format for example. The only thing to do here
            # is defining the targeted version.
            self.version = ArtifactVersion(
                f"{self.defs.version(self.derivative)}-{self.defs.release}"
            )
            return
        else:
            # If the source tarball has not been provided and the artifact is
            # defined with a source tarball URL, it is downloaded in cache (if
            # not already present) using this URL.

            # The targeted version is fully defined based on definition
            self.version = ArtifactVersion(
                f"{self.defs.version(self.derivative)}-{self.defs.release}"
            )
            if not self.cache.has_tarball:
                dl_file(self.tarball_url, self.cache.tarball)

            verify_checksum(
                self.cache.tarball,
                self.checksum_format,
                self.checksum_value,
            )

            logger.info(
                "Using artifact source tarball from cache %s",
                self.cache.tarball,
            )
            self.tarball = self.cache.tarball

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
    def prescript_tarballs(self):
        """Returns the list of subfolders generated in prescripts to include in
        supplementary tarballs."""
        return self.prescript_token('TARBALLS')

    def prescript_in_env(self, tarball_subdir):
        """Method to run the prescript in build environment. This method must
        be implemented at format specialized classes level."""
        raise NotImplementedError

    def prescript_supp_tarball(self, tarball_subdir):
        """Method to generate the prescript supplementary tarballs. This method
        must be implemented at format specialized classes level."""
        raise NotImplementedError

    def prescript_supp_subdir_renamed(self, subdir):
        """Returns the name (string format) to uniquely timestamped renamed
        supplementary tarball subdirectory."""
        return f"{subdir}-{date.today().strftime('%Y%m%d')}-{self.id[:8]}"

    def prescript(self):
        """Run the prescript."""

        # Check the prescript is present or leave
        if not self.prescript_path.exists():
            logger.debug(
                "Prescript no found, continuing with unmodified tarball"
            )
            return

        logger.info("Running the prescript")

        # Create temporary upstream directory
        upstream_dir = self.place.joinpath('upstream')
        upstream_dir.mkdir()

        # Extract original upstream tarball (and get the subdir)
        with tarfile.open(self.tarball) as tar:
            tar_safe_extractall(tar, upstream_dir)
            tarball_subdir = upstream_dir.joinpath(tar_subdir(tar))

        # Remove .gitignore file if present, to avoid modification realized
        # by pre script being ignored when generating the resulting patch.
        gitignore_path = tarball_subdir.joinpath('.gitignore')
        if gitignore_path.exists():
            logger.info("Removing .gitignore from upstream archive")
            gitignore_path.unlink()

        # init the git repository with its initial commit
        git = GitRepository(tarball_subdir, self.user, self.email)

        # import existing patches in queue
        if self.has_patches:
            git.import_patches(self.patches_dir, self.version.main)

        # Now run the prescript!
        self.prescript_in_env(tarball_subdir)

        if len(self.prescript_tarballs):
            # Rename and symlink prescript tarballs subdirectories with unique
            # timestamped names, so the resulting supplementary tarball name is
            # also unique and cannot conflict in targeted package repository
            # with another existing supplementary tarball with different
            # content.
            for subdir in self.prescript_tarballs:
                subdir_path = tarball_subdir.joinpath(subdir)
                target = tarball_subdir.joinpath(
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
            self.prescript_supp_tarball(tarball_subdir)
            # Export patch with symlinks in patch queue
            git.commit_export(
                self.patches_dir.joinpath(self.version.main),
                9999,
                'fatbuildr-prescript-symlinks',
                self.user,
                self.email,
                "Patch generated by fatbuildr to symlink prescript "
                "supplementary tarballs subdirectories",
                files=self.prescript_tarballs,
            )
        else:
            # Export git repo diff in patch queue
            git.commit_export(
                self.patches_dir.joinpath(self.version.main),
                9999,
                'fatbuildr-prescript',
                self.user,
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
