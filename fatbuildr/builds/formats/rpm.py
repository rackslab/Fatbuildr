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
import tarfile

from .. import ArtifactEnvBuild
from ...registry.formats import ChangelogEntry
from ...templates import Templeter
from ...utils import current_user, current_group, tar_subdir
from ...log import logr

logger = logr(__name__)

# String template for changelog in RPM spec file
SOURCES_DECL_TPL = """
Source: {{ main_tarball }}
{% for tarball in supplementary_tarballs %}
Source{{ loop.index }}: {{ tarball }}
{% endfor %}
"""

SOURCES_PREP_TPL = """
%setup -q -n {{ main_tarball_subdir }}
{% for tarball in supplementary_tarballs %}
%setup -T -D -n {{ main_tarball_subdir }} -a {{ loop.index }}
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
        src_tarball,
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
        """Returns the path to the source subdirectory used as input by mock for
        building the SRPM. The directory is created if not already present."""
        path = self.place.joinpath('source')
        if not path.exists():
            logger.debug("Create source subdirectory %s", path)
            path.mkdir()
            path.chmod(0o755)
        return path

    def supp_tarball_path(self, subdir):
        """Returns the patch to the supplementary tarball for the given
        subdir."""
        return self.source_path.joinpath(
            f"{self.artifact}_{self.version.main}-"
            f"{self.prescript_supp_subdir_renamed(subdir)}.tar.xz",
        )

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
        sources_decl = ""
        sources_prep = ""
        patches_decl = ""
        patches_prep = ""

        sources_decl = templater.srender(
            SOURCES_DECL_TPL,
            main_tarball=self.tarball.name,
            supplementary_tarballs=[
                self.supp_tarball_path(subdir).name
                for subdir in self.prescript_tarballs
            ],
        )

        sources_prep = templater.srender(
            SOURCES_PREP_TPL,
            main_tarball_subdir=tar_subdir(self.tarball),
            supplementary_tarballs=self.prescript_tarballs,
        )

        if not self.patches_dir.empty:
            # Move patches in the sources subdirectory
            for patch in self.patches:
                patch.rename(self.source_path.joinpath(patch.name))
            patches_decl = templater.srender(
                PATCHES_DECL_TPL, patches=self.patches
            )
            patches_prep = templater.srender(
                PATCHES_PREP_TPL, patches=self.patches
            )

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
                    source=sources_decl,
                    prep_sources=sources_prep,
                    patches=patches_decl,
                    prep_patches=patches_prep,
                    changelog=changelog,
                )
            )

        # If the source tarball is not in build place (ie. in cache),
        # create symlink of the source tarball in the sources subdirectory (the
        # cache directory is then bind-mounted in the mock environment).
        # Otherwise, move the tarball from the build place to the sources
        # subdirectory.
        source = self.source_path.joinpath(self.tarball.name)
        if not self.tarball_in_build_place:
            logger.info("Creating symlink %s → %s", source, self.tarball)
            source.symlink_to(self.tarball)
        else:
            logger.info("Moving tarball from %s to %s", self.tarball, source)
            self.tarball = self.tarball.rename(source)

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

        # If the source tarball is not in build place (ie. in cache),
        # bind-mount the tarball directory in mock environment so rpmbuild can
        # access to the target of the tarball symlink in build place.
        if not self.tarball_in_build_place:
            cmd[3:3] = [
                '--plugin-option',
                "bind_mount:dirs="
                f"[(\"{self.tarball.parent}\",\"{self.tarball.parent}\")]",
            ]

        self.cruncmd(cmd)

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
            '--resultdir',
            self.place,
            '--rebuild',
            self.srpm_path,
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

    def prescript_in_env(self, tarball_subdir):
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

        try:
            # install deps
            logger.debug(
                "Installing prescript dependencies in build environment %s: %s",
                self.native_env.name,
                self.prescript_deps,
            )

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
                '--dnf-cmd',
                'install',
            ] + self.prescript_deps
            self.cruncmd(cmd)

            logger.debug(
                "Running the prescript using stage1 script in build environment %s",
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
                f"FATBUILDR_SOURCE_DIR={tarball_subdir}",
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

    def prescript_supp_tarball(self, tarball_subdir):
        for subdir in self.prescript_tarballs:
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
