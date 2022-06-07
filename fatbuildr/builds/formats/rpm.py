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
from pathlib import Path

from .. import ArtifactEnvBuild
from ...registry.formats import ChangelogEntry
from ...templates import Templeter
from ...utils import current_user, current_group
from ...log import logr

logger = logr(__name__)

# String template for changelog in RPM spec file
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
{% for patch in patches %}
%patch{{ loop.index0 }} -p1
{% endfor %}
"""

# Jinja2 filter to convert timestamp to date formatted for RPM spec file
# changelog entries.
def timestamp_rpmdate(value):
    return datetime.fromtimestamp(value).strftime("%a %b %d %Y")


class ArtifactBuildRpm(ArtifactEnvBuild):
    """Class to manipulation package in RPM format."""

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
        super().__init__(
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
        )

    @property
    def spec_basename(self):
        return self.artifact + '.spec'

    @property
    def srpm_filename(self):
        return self.artifact + '-' + self.version.full + '.src.rpm'

    @property
    def srpm_path(self):
        return self.place.joinpath(self.srpm_filename)

    @property
    def source_path(self):
        return self.place.joinpath('source')

    def build(self):
        self._build_src()
        for architecture in self.architectures:
            self._build_bin(architecture)

    def _build_src(self):
        """Build source SRPM"""

        logger.info(
            "Building source RPM for %s in build environment %s",
            self.artifact,
            self.native_env,
        )

        # Add distribution release tag to targeted version
        self.version.dist = self.instance.pipelines.dist_tag(self.distribution)

        # Initialize templater
        templater = Templeter()

        # Generate patches templates
        patches_decl = ""
        patches_prep = ""

        if not self.source_path.exists():
            logger.debug("Create source subdirectory %s", self.source_path)
            self.source_path.mkdir()
            self.source_path.chmod(0o755)

        if self.has_patches:
            # Move patches at the root of build place
            patches = self.patches
            for patch in patches:
                patch.rename(self.source_path.joinpath(patch.name))
            patches_decl = templater.srender(PATCHES_DECL_TPL, patches=patches)
            patches_prep = templater.srender(PATCHES_PREP_TPL, patches=patches)

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
                f"{self.user} <{self.email}>",
                datetime.now().timestamp(),
                [self.message],
            )
        ]
        if existing_version:
            new_changelog.extend(existing_changelog)

        # Render changelog based on string template
        templater.env.filters["timestamp_rpmdate"] = timestamp_rpmdate
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
                    source=self.tarball.name,
                    patches=patches_decl,
                    prep_patches=patches_prep,
                    changelog=changelog,
                )
            )

        # Check the tarball is in build place (ie. not in cache), or create
        # symlink otherwise, so the source tarball given to mock is always in
        # the same directory as the patches, when patches are provided.
        source = self.source_path.joinpath(self.tarball.name)
        logger.info("Creating symlink %s → %s", source, self.tarball)
        source.symlink_to(self.tarball)

        # run SRPM build
        cmd = [
            'mock',
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

        # If the source tarball is not in build place (ie. in cache),
        # bind-mount the tarball directory in mock environment so rpmbuild can
        # access to the target of the tarball symlink in build place.
        if not self.tarball.is_relative_to(self.place):
            cmd[3:3] = [
                '--plugin-option',
                "bind_mount:dirs="
                f"[(\"{self.tarball.parent}\",\"{self.tarball.parent}\")]",
            ]

        self.cruncmd(cmd, user=current_user()[1])

    def _build_bin(self, architecture):
        """Build binary RPM"""

        env = self.instance.images_mgr.build_env(
            self.format, self.env_name, architecture
        )
        logger.info(
            "Building binary RPM based on %s in build environment %s",
            self.srpm_path,
            env,
        )

        cmd = [
            'mock',
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
            '--resultdir',
            self.place,
            '--rebuild',
            self.srpm_path,
        ]

        # Add additional build args if defined
        if self.defs.has_buildargs:
            cmd.extend(self.defs.buildargs)

        self.cruncmd(cmd, user=current_user()[1])

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

    def _mock_overlay_cmd(self, _cmd):
        """Run mock overlayfs snapshot related command on host native build
        environment."""
        cmd = [
            'mock',
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
        self.cruncmd(cmd, user=current_user()[1])

    def prescript_in_env(self, tarball_subdir):
        """Execute prescript in RPM build environment using mock and
        snapshots."""
        logger.info(
            "Executing prescript in deb build environment %s",
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

        try:
            # install deps
            deps = list(set(['wget'] + self.prescript_deps))
            logger.debug(
                "Installing prescript dependencies in build environment %s: %s",
                self.native_env.name,
                deps,
            )

            cmd = [
                'mock',
                '--root',
                self.native_env.name,
                '--dnf-cmd',
                'install',
            ] + deps
            self.cruncmd(cmd, user=current_user()[1])

            logger.debug(
                "Running the prescript using stage1 script in build environment %s",
                self.native_env.name,
            )

            # run prescript
            cmd = [
                'mock',
                '--root',
                self.native_env.name,
                '--config-opts',
                f"chrootuid={current_user()[0]}",
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
                '--plugin-option',
                "bind_mount:dirs="
                f"[(\"{self.place}\",\"{self.place}\"),"
                f"(\"{self.image.common_libdir}\",\"{self.image.common_libdir}\")]",
                '--shell',
                '--',
                f"FATBUILDR_SOURCE_DIR={tarball_subdir}",
                '/bin/bash',
                self.image.common_libdir.joinpath('pre-stage1-rpm.sh'),
                self.prewrapper_path,
                self.prescript_path,
            ]
            self.cruncmd(cmd, user=current_user()[1])
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
