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

from datetime import datetime

from .. import ArtifactEnvBuild
from ...registry.formats import ChangelogEntry
from ...templates import Templeter
from ...utils import current_user, current_group
from ...errors import FatbuildrTaskExecutionError
from ...log import logr

logger = logr(__name__)

# String template for changelog in RPM spec file
SOURCES_DECL_TPL = """
{% for source in sources %}
Source{{ loop.index0 }}: {{ source.path.name }}
{% endfor %}
{% for plain_file in plain_files %}
Source{{ loop.index0 + sources|length }}: {{ plain_file.name }}
{% endfor %}
"""

SOURCES_PREP_TPL = """
%setup -q -n {{ main_tarball_subdir }}
{% for source in supplementary_sources %}
{% if source.has_single_toplevel %}
%setup -T -D -n {{ main_tarball_subdir }} -a {{ loop.index }}
mv {{ source.subdir }} {{ source.sanitized_stem }}
{% else %}
%setup -T -D -n {{ main_tarball_subdir }} -a {{ loop.index }} -c
{% endif %}
{% endfor %}
{% for source in prescript_sources %}
%setup -T -D -n {{ main_tarball_subdir }} -a {{ loop.index + supplementary_sources|length }}
{% endfor %}
"""

CHANGELOG_TPL = """
%changelog
{% for entry in changelog %}
* {{ entry.date|timestamp_rpmdate }} {{ entry.author }} {{ entry.version }}
  {% for change in entry.changes %}
- {{ change }}
  {% endfor %}

{% endfor %}
"""

PATCHES_DECL_TPL = """
{% for patch in patches %}
Patch{{ loop.index0 }}: {{ patch.name }}
{% endfor %}
"""

PATCHES_PREP_TPL = """
%autopatch -p1
"""


class ArtifactBuildRpm(ArtifactEnvBuild):
    """Class to manipulation package in RPM format."""

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
        )

    @property
    def spec_basename(self):
        return self.artifact + '.spec'

    def srpm_path(self):
        """Return first *.src.rpm found in build place."""
        for srpm in self.place.glob(f"{self.artifact}-*.src.rpm"):
            return srpm

    @property
    def source_path(self):
        """Returns the path to the source subdirectory used as input by mock for
        building the SRPM. The directory is created if not already present."""
        path = self.place.joinpath('source')
        if not path.exists():
            logger.debug("Create source subdirectory %s", path)
            path.mkdir()
            path.chmod(0o755)
        return path

    def supp_tarball_path(self, subdir):
        """Returns the path to the supplementary tarball for the given
        subdir."""
        return self.source_path.joinpath(
            f"{self.artifact}_{self.version.main}-"
            f"{self.prescript_supp_subdir_renamed(subdir)}.tar.xz",
        )

    def build(self):
        self.check_image_exists()
        self._build_src()
        for architecture in self.architectures:
            self._build_bin(architecture)
        self._static_check()

    def _build_src(self):
        """Build source SRPM"""
        self.check_build_env_exists()

        logger.info(
            "Building source RPM for %s in build environment %s",
            self.artifact,
            self.native_env,
        )

        if self.main_archive is None:
            raise FatbuildrTaskExecutionError(
                f"Main archive of rpm package artifact {self.artifact} is not "
                "defined"
            )

        # Initialize templater
        templater = Templeter()

        # Generate patches templates
        sources_decl = ""
        sources_prep = ""
        patches_decl = ""
        patches_prep = ""

        plain_files = [
            path
            for path in self.place.joinpath('rpm').glob('*')
            if path.is_file() and path.name != self.spec_basename
        ]
        if len(plain_files):
            logger.debug(
                "Found additional plain files as sources for source RPM: %s",
                plain_files,
            )

        sources_decl = templater.srender(
            SOURCES_DECL_TPL,
            sources=self.archives + self.prescript_tarballs,
            plain_files=plain_files,
        )

        sources_prep = templater.srender(
            SOURCES_PREP_TPL,
            main_tarball_subdir=self.main_archive.subdir,
            supplementary_sources=self.supplementary_archives,
            prescript_sources=self.prescript_tarballs,
        )

        if not self.patches_dir.empty:
            # Move patches in the sources subdirectory
            for patch in self.patches:
                patch.rename(self.source_path.joinpath(patch.name))
            patches_decl = templater.srender(
                PATCHES_DECL_TPL, patches=self.patches
            )
            patches_prep = PATCHES_PREP_TPL

        # Check if existing source package and get version
        existing_version = self.registry.source_version(
            self.distribution, self.derivative, self.artifact
        )
        if existing_version:
            logger.info(
                "Found existing version %s, extracting changelog entries",
                existing_version.full,
            )
            # Source package is already present, get existing changelog
            existing_changelog = self.registry.changelog(
                self.distribution, self.derivative, 'src', self.artifact
            )

            # Compare existing version with the target version
            if existing_version == self.version:
                logger.info(
                    "Incrementing build number of existing version %s",
                    existing_version.full,
                )
                # use the increment existing version as new fullversion
                self.version.build = existing_version.build + 1

        # Generate a new list of ChangelogEntry, extended with existing entries
        # if present.
        new_changelog = [
            ChangelogEntry(
                self.version.full,
                f"{self.author} <{self.email}>",
                datetime.now().timestamp(),
                [
                    self.message,
                    self.changelog_task_entry,
                ],
            )
        ]
        if existing_version:
            new_changelog.extend(existing_changelog)

        # Render changelog based on string template
        changelog = templater.srender(CHANGELOG_TPL, changelog=new_changelog)

        # Generate spec file based on template
        spec_tpl_path = self.place.joinpath('rpm', self.spec_basename)
        spec_path = self.place.joinpath(self.spec_basename)

        if not spec_tpl_path.exists():
            raise RuntimeError(
                f"RPM spec template file {spec_tpl_path} does not exist"
            )

        logger.debug(
            "Generate RPM spec file %s based on %s", spec_path, spec_tpl_path
        )
        with open(spec_path, 'w+') as fh:
            fh.write(
                templater.frender(
                    spec_tpl_path,
                    pkg=self,
                    version=self.version.main,
                    release=self.version.fullrelease,
                    sources=sources_decl,
                    prep_sources=sources_prep,
                    patches=patches_decl,
                    prep_patches=patches_prep,
                    prep=sources_prep + patches_prep,
                    changelog=changelog,
                )
            )

        # If the source archive is not in build place (ie. in cache),
        # create symlink of the source archive in the sources subdirectory (the
        # cache directory is then bind-mounted in the mock environment).
        # Otherwise, move the source archive from the build place to the sources
        # subdirectory.
        need_bind_mount_cache = False
        for archive in self.archives:
            source = self.source_path.joinpath(archive.path.name)
            if not self.archive_in_build_place(archive):
                need_bind_mount_cache = True
                logger.info("Creating symlink %s → %s", source, archive.path)
                source.symlink_to(archive.path)
            else:
                logger.info(
                    "Moving source archive from %s to %s", archive.path, source
                )
                archive.path = archive.path.rename(source)

        for plain_file in plain_files:
            source = self.source_path.joinpath(plain_file.name)
            logger.info(
                "Moving source archive from %s to %s", plain_file, source
            )
            plain_file = plain_file.rename(source)

        # run SRPM build
        cmd = [
            self.image.builder,
            '--root',
            self.native_env.name,
            '--config-opts',
            f"chrootgid={current_group()[0]}",
            '--buildsrpm',
            '--sources',
            self.source_path,
            '--spec',
            spec_path,
            '--resultdir',
            self.place,
        ]

        # Bind-mount the artifact cache directory in mock environment so
        # rpmbuild can access to the target of the archives symlinks in build
        # place if needed.
        if need_bind_mount_cache:
            cmd[3:3] = [
                '--plugin-option',
                "bind_mount:dirs="
                f"[(\"{self.cache.dir}\",\"{self.cache.dir}\")]",
            ]

        self.cruncmd(cmd)

    def _build_bin(self, architecture):
        """Build binary RPM"""

        self.check_build_env_exists(architecture)
        env = self.instance.images_mgr.build_env(
            self.format, self.env_name, architecture
        )
        logger.info(
            "Building binary RPM based on %s in build environment %s",
            self.srpm_path(),
            env,
        )

        cmd = [
            self.image.builder,
            '--root',
            env.name,
            '--config-opts',
            f"chrootgid={current_group()[0]}",
            '--enable-plugin',
            'fatbuildr_derivatives',
            '--plugin-option',
            f"fatbuildr_derivatives:repo={self.registry.path}",
            '--plugin-option',
            f"fatbuildr_derivatives:distribution={self.distribution}",
            '--plugin-option',
            f"fatbuildr_derivatives:derivatives={','.join(self.derivatives)}",
            '--plugin-option',
            f"fatbuildr_derivatives:keyring={self.build_keyring}",
            '--enable-plugin',
            'fatbuildr_interactive',
            '--plugin-option',
            'fatbuildr_interactive:enabled='
            f"{'yes' if self.io.interactive else 'no'}",
            '--enable-plugin',
            'fatbuildr_list',
            '--resultdir',
            self.place,
            '--rebuild',
            self.srpm_path(),
        ]

        # Add additional build args if defined
        if self.defs.has_buildargs:
            cmd.extend(self.defs.buildargs)

        self.cruncmd(cmd)

        # Load keys in agent prior to signing
        self.instance.keyring.load_agent()

        # sign all RPM packages, including SRPM
        for rpm_path in self.place.glob('*.rpm'):
            logger.debug(
                "Signing RPM %s with key %s",
                rpm_path,
                self.instance.keyring.masterkey.fingerprint,
            )
            cmd = [
                'rpmsign',
                '--define',
                '%__gpg /usr/bin/gpg',
                '--define',
                '%_gpg_name ' + self.instance.keyring.masterkey.userid,
                '--addsign',
                rpm_path,
            ]
            self.runcmd(
                cmd, env={'GNUPGHOME': str(self.instance.keyring.homedir)}
            )

    def _static_check(self):
        """Run with rpmlint for static analysis on all built RPM packages,
        including the source package."""
        packages = list(self.place.glob('*.rpm'))
        logger.info(
            "Running static analysis on generated RPM packages: %s",
            ' '.join(package.name for package in packages),
        )
        cmd = ['rpmlint', '--info', '--permissive'] + packages
        self.cruncmd(cmd)

    def _mock_overlay_cmd(self, _cmd):
        """Run mock overlayfs snapshot related command on host native build
        environment."""
        cmd = [
            self.image.builder,
            '--root',
            self.native_env.name,
            '--enable-plugin',
            'overlayfs',
            '--disable-plugin',
            'root_cache',
            '--plugin-option',
            'overlayfs:base_dir=/var/lib/snapshots',
        ]
        cmd.extend(_cmd)
        self.cruncmd(cmd)

    def prescript_in_env(self, archive_subdir):
        """Execute prescript in RPM build environment using mock and
        snapshots."""
        logger.info(
            "Executing prescript in rpm build environment %s",
            self.native_env.name,
        )

        # create snapshot
        logger.debug(
            "Creating snapshot %s of build environment %s",
            self.id,
            self.native_env.name,
        )
        self._mock_overlay_cmd(['--snapshot', self.id])

        prescript_failed = False

        module_prefix = 'module:'
        prescript_modules_deps = [
            dep[len(module_prefix) :]
            for dep in self.prescript_deps
            if dep.startswith(module_prefix)
        ]
        prescript_pkgs_deps = [
            dep
            for dep in self.prescript_deps
            if not dep.startswith(module_prefix)
        ]

        def run_mock_dnf_cmd(args):
            cmd = [
                self.image.builder,
                '--root',
                self.native_env.name,
                '--enable-plugin',
                'fatbuildr_derivatives',
                '--plugin-option',
                f"fatbuildr_derivatives:repo={self.registry.path}",
                '--plugin-option',
                f"fatbuildr_derivatives:distribution={self.distribution}",
                '--plugin-option',
                f"fatbuildr_derivatives:derivatives={','.join(self.derivatives)}",
                '--plugin-option',
                f"fatbuildr_derivatives:keyring={self.build_keyring}",
                '--enable-network',
                '--dnf-cmd',
            ] + args
            self.cruncmd(cmd)

        try:
            # Install packages dependencies, if any.
            if len(prescript_pkgs_deps):
                logger.debug(
                    "Installing prescript packages dependencies in build environment "
                    "%s: %s",
                    self.native_env.name,
                    prescript_pkgs_deps,
                )

                run_mock_dnf_cmd(['install'] + prescript_pkgs_deps)

            # Install modules dependencies, if any.
            if len(prescript_modules_deps):
                logger.debug(
                    "Installing prescript modules dependencies in build environment "
                    "%s: %s",
                    self.native_env.name,
                    prescript_modules_deps,
                )
                run_mock_dnf_cmd(['module', 'install'] + prescript_modules_deps)

            logger.debug(
                "Running the prescript using stage1 script in build "
                "environment %s",
                self.native_env.name,
            )

            # run prescript
            cmd = [
                self.image.builder,
                '--root',
                self.native_env.name,
                '--config-opts',
                f"chrootuid={current_user()[0]}",
                '--config-opts',
                f"chrootgid={current_group()[0]}",
                '--plugin-option',
                "bind_mount:dirs="
                f"[(\"{self.place}\",\"{self.place}\"),"
                f"(\"{self.image.common_libdir}\",\"{self.image.common_libdir}\")]",
                '--shell',
                '--',
                f"FATBUILDR_SOURCE_DIR={archive_subdir}",
                '/bin/bash',
                self.image.common_libdir.joinpath('pre-stage1-rpm.sh'),
                self.prewrapper_path,
                self.prescript_path,
            ]
            self.cruncmd(cmd)
        except RuntimeError as err:
            logger.error("Error while running prescript: %s", err)
            prescript_failed = True
        finally:
            # clean snapshot
            logger.debug(
                "Cleaning snapshot %s of build environment %s",
                self.id,
                self.native_env.name,
            )
            self._mock_overlay_cmd(['--clean'])

            # scrub overlayfs
            logger.debug("Scrubing data of mock overlayfs plugin")
            self._mock_overlay_cmd(['--scrub', 'overlayfs'])

        # Now that mock snapshot are cleaned for sure, RuntimeError can be
        # raised to report the task as failed in case dep installation and
        # prescript had errors.
        if prescript_failed:
            raise RuntimeError("prescript error")
