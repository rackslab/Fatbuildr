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

from .. import ArtefactBuild
from ...registry.formats import ChangelogEntry
from ...templates import Templeter
from ...log import logr

logger = logr(__name__)

# String template for changelog in RPM spec file
CHANGELOG_TPL = """
%changelog
{%- for entry in changelog %}
* {{ entry.date|timestamp_rpmdate }} {{ entry.author }} {{ entry.version }}
  {%- for change in entry.changes %}
- {{ change }}
  {%- endfor %}
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


class ArtefactBuildRpm(ArtefactBuild):
    """Class to manipulation package in RPM format."""

    def __init__(
        self,
        task_id,
        place,
        instance,
        format,
        distribution,
        derivative,
        artefact,
        user_name,
        user_email,
        message,
        tarball,
        src_tarball,
    ):
        super().__init__(
            task_id,
            place,
            instance,
            format,
            distribution,
            derivative,
            artefact,
            user_name,
            user_email,
            message,
            tarball,
            src_tarball,
        )
        self.format = 'rpm'

    @property
    def spec_basename(self):
        return self.artefact + '.spec'

    @property
    def srpm_filename(self):
        return self.artefact + '-' + self.version.full + '.src.rpm'

    @property
    def srpm_path(self):
        return self.place.joinpath(self.srpm_filename)

    def build(self):
        self._build_src()
        self._build_bin()

    def _build_src(self):
        """Build source SRPM"""

        logger.info(
            "Building source RPM for %s in environment %s",
            self.artefact,
            self.env.name,
        )

        # Add distribution to targeted version
        self.version.dist = self.distribution

        # Initialize templater
        templater = Templeter()

        # Generate patches templates
        patches_decl = ""
        patches_prep = ""

        if self.has_patches:
            # Move patches at the root of build place
            patches = self.patches
            for patch in patches:
                patch.rename(self.place.joinpath(patch.name))
            patches_decl = templater.srender(PATCHES_DECL_TPL, patches=patches)
            patches_prep = templater.srender(PATCHES_PREP_TPL, patches=patches)

        # Check if existing source package and get version
        existing_version = self.registry.source_version(
            self.distribution, self.derivative, self.artefact
        )
        if existing_version:
            logger.info(
                "Found existing version %s, extracting changelog entries",
                existing_version.full,
            )
            # Source package is already present, get existing changelog
            existing_changelog = self.registry.changelog(
                self.distribution, self.derivative, 'src', self.artefact
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
        if not self.tarball.is_relative_to(self.place):
            source = self.place.joinpath(self.tarball.name)
            logger.info("Creating symlink %s → %s", source, self.tarball)
            source.symlink_to(self.tarball)

        # run SRPM build
        cmd = [
            'mock',
            '--root',
            self.env.name,
            '--buildsrpm',
            '--sources',
            self.place,
            '--spec',
            spec_path,
            '--resultdir',
            self.place,
        ]

        # If the source tarball is in build place (ie. in cache),
        # bind-mount the tarball directory in mock environment so rpmbuild can
        # access to the target of the tarball symlink in build place.
        if not self.tarball.is_relative_to(self.place):
            cmd[3:3] = [
                '--plugin-option',
                "bind_mount:dirs="
                f"[(\"{self.tarball.parent}\",\"{self.tarball.parent}\")]",
            ]

        self.cruncmd(cmd)

    def _build_bin(self):
        """Build binary RPM"""

        logger.info(
            "Building binary RPM based on %s in environment %s",
            self.srpm_path,
            self.env.name,
        )

        # Save keyring in build place so dnf can check signatures of
        # fatbuildr packages in mock environment.
        keyring_path = self.place.joinpath('keyring.asc')
        with open(keyring_path, 'w+') as fh:
            fh.write(self.instance.keyring.export())

        cmd = [
            'mock',
            '--root',
            self.env.name,
            '--enable-plugin',
            'fatbuildr_derivatives',
            '--plugin-option',
            f"fatbuildr_derivatives:repo={self.registry.path}",
            '--plugin-option',
            f"fatbuildr_derivatives:distribution={self.distribution}",
            '--plugin-option',
            f"fatbuildr_derivatives:derivatives={','.join(self.derivatives)}",
            '--plugin-option',
            f"fatbuildr_derivatives:keyring={keyring_path}",
            '--resultdir',
            self.place,
            '--rebuild',
            self.srpm_path,
        ]

        # Add additional build args if defined
        if self.has_buildargs:
            cmd.extend(self.buildargs)

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
