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

import tarfile
import email
from pathlib import Path

from debian import deb822, changelog, debfile

from . import Registry, ArtifactVersion, RegistryArtifact, ChangelogEntry
from ...templates import Templeter
from ...utils import runcmd
from ...log import logr

logger = logr(__name__)


class RegistryDeb(Registry):
    """Registry for Deb format (aka. APT repository)."""

    def __init__(self, conf, instance):
        super().__init__(conf, instance, 'deb')

    @property
    def distributions(self):
        dists_path = self.path.joinpath('dists')
        if not dists_path.exists():
            return []
        return [item.name for item in dists_path.iterdir()]

    @property
    def components(self):
        pool_path = self.path.joinpath('pool')
        if not pool_path.exists():
            return []
        return [item.name for item in pool_path.iterdir()]

    @property
    def dists_conf(self):
        return self.path.joinpath('conf', 'distributions')

    def derivatives(self, distribution):
        return self.components

    def publish(self, build):
        """Publish both source and binary package in APT repository."""

        logger.info(
            "Publishing Deb packages for %s in distribution %s",
            build.artifact,
            build.distribution,
        )

        # load reprepro distributions template
        dists_tpl_path = self.conf.registry.conf.joinpath(
            'apt', 'distributions.j2'
        )

        # create parent directory recursively, if not present
        if not self.dists_conf.parent.exists():
            self.dists_conf.parent.mkdir(parents=True)

        # generate reprepro distributions file
        logger.debug("Generating distribution file %s", self.dists_conf)
        # Combine existing distributions in repository with build distribution
        # to define resulting list of distributions.
        distributions = list(set(self.distributions + [build.distribution]))
        components = list(set(self.components + build.derivatives))
        architectures = [
            self.archmap.native(architecture)
            for architecture in self.instance.pipelines.architectures
        ]
        with open(self.dists_conf, 'w+') as fh:
            fh.write(
                Templeter().frender(
                    dists_tpl_path,
                    distributions=distributions,
                    architectures=architectures,
                    components=components,
                    key=self.instance.keyring.masterkey.subkey.fingerprint,
                    instance=self.instance.name,
                )
            )

        # Load keyring in agent so repos are signed with new packages
        self.instance.keyring.load_agent()

        # Check packages are not already present in this distribution of the
        # repository with this version before trying to publish them, or fail
        # when it is the case.
        logger.debug(
            "Checking if package %s is already present in distribution %s",
            build.artifact,
            build.distribution,
        )
        cmd = [
            'reprepro',
            '--basedir',
            self.path,
            '--list-format',
            '${version}',
            'list',
            build.distribution,
            build.artifact,
        ]

        for changes_path in build.place.glob('*.changes'):
            # Skip source changes, source package is published in repository as
            # part of binary changes.
            if changes_path.match('*_source.changes'):
                continue
            logger.debug("Publishing deb changes file %s", changes_path)
            cmd = [
                'reprepro',
                '--verbose',
                '--basedir',
                self.path,
                '--component',
                build.derivative,
                'include',
                build.distribution,
                changes_path,
            ]
            build.runcmd(
                cmd, env={'GNUPGHOME': str(self.instance.keyring.homedir)}
            )

    def artifacts(self, distribution, derivative):
        """Returns the list of artifacts in deb repository."""

        # Check if repository distributions configuration file exists. If this
        # file does not exist, the repository is necessarily empty.
        if not self.dists_conf.exists():
            return []

        artifacts = []
        cmd = [
            'reprepro',
            '--basedir',
            self.path,
            '--component',
            derivative,
            '--list-format',
            '${package}|${Architecture}|${$architecture}|${version}\n',
            'list',
            distribution,
        ]
        repo_list_proc = runcmd(cmd)
        lines = repo_list_proc.stdout.decode().strip().split('\n')
        for line in lines:
            if not line:
                continue
            (name, arch, locarch, version) = line.split('|')
            if locarch == 'source':
                _arch = locarch
            else:
                _arch = arch
            artifact = RegistryArtifact(
                name, self.archmap.normalized(_arch), version
            )
            # Architecture independant packages can appear multiple times in
            # reprepro command output as their duplicated for every
            # ${$architecture} in repository. We check the RegistryArtifact
            # is not already present in list to avoid duplicated entries in
            # resulting list.
            if artifact not in artifacts:
                artifacts.append(artifact)
        return artifacts

    def artifact_bins(self, distribution, derivative, src_artifact):
        """Returns the list of binary deb packages generated by the given source
        deb package."""
        artifacts = []
        cmd = [
            'reprepro',
            '--basedir',
            self.path,
            '--component',
            derivative,
            '--list-format',
            '${package}|${Architecture}|${$architecture}|${$source}|${version}\n',
            'list',
            distribution,
        ]
        repo_list_proc = runcmd(cmd)
        lines = repo_list_proc.stdout.decode().strip().split('\n')
        for line in lines:
            (name, arch, locarch, source, version) = line.split('|')
            if locarch == 'source':  # skip non-binary package
                continue
            if source != src_artifact:
                continue
            artifact = RegistryArtifact(
                name, self.archmap.normalized(arch), version
            )
            # Architecture independant packages can appear multiple times in
            # reprepro command output as their duplicated for every
            # ${$architecture} in repository. We check the RegistryArtifact
            # is not already present in list to avoid duplicated entries in
            # resulting list.
            if artifact not in artifacts:
                artifacts.append(artifact)
        return artifacts

    def artifact_src(self, distribution, derivative, bin_artifact):
        """Returns the source dsc package that generated the given binary deb
        package."""
        cmd = [
            'reprepro',
            '--basedir',
            self.path,
            '--component',
            derivative,
            '--list-format',
            '${$architecture}|${$source}|${version}\n',
            'list',
            distribution,
            bin_artifact,
        ]
        repo_list_proc = runcmd(cmd)
        lines = repo_list_proc.stdout.decode().strip().split('\n')
        for line in lines:
            (locarch, source, version) = line.split('|')
            if locarch == 'source':  # skip source package
                continue
            return RegistryArtifact(source, 'src', version)

    def source_version(self, distribution, derivative, artifact):
        """Returns the version of the given source package name, or None if not
        found."""
        # Check if repository distributions configuration file exists. If this
        # file does not exist, the repository is necessarily empty.
        if not self.dists_conf.exists():
            return None

        # Check if the build distribution is already present in repository. If
        # not, the source version is necessarily None.
        if distribution not in self.distributions:
            return None

        # Check if the derivative exists in the repository. If not, the
        # associated component pool is necessarily empty.
        if derivative not in self.derivatives(distribution):
            return None

        cmd = [
            'reprepro',
            '--basedir',
            self.path,
            '--component',
            derivative,
            '--list-format',
            '${$architecture}|${version}\n',
            'list',
            distribution,
            artifact,
        ]
        repo_list_proc = runcmd(cmd)
        lines = repo_list_proc.stdout.decode().strip().split('\n')
        for line in lines:
            if not line:
                continue
            (locarch, version) = line.split('|')
            if locarch != 'source':  # skip binary package
                continue
            return ArtifactVersion(version)
        return None

    def _package_dsc_path(self, distribution, derivative, src_artifact):
        """Returns the path to the dsc file of the given deb source package."""
        cmd = [
            'reprepro',
            '--basedir',
            self.path,
            '--component',
            derivative,
            '--list-format',
            '${$architecture}|${$fullfilename}\n',
            'list',
            distribution,
            src_artifact,
        ]
        repo_list_proc = runcmd(cmd)
        lines = repo_list_proc.stdout.decode().strip().split('\n')
        for line in lines:
            (locarch, pkg_path) = line.split('|')
            if locarch != 'source':  # skip binary package
                continue
            return Path(pkg_path)
        raise RuntimeError(
            f"Unable to find dsc path for deb source package {src_artifact}"
        )

    def _package_deb_path(
        self, distribution, derivative, architecture, bin_artifact
    ):
        """Returns the path to the deb file of the given deb binary package."""
        cmd = [
            'reprepro',
            '--basedir',
            self.path,
            '--component',
            derivative,
            '--list-format',
            '${Architecture}|${$fullfilename}\n',
            'list',
            distribution,
            bin_artifact,
        ]
        repo_list_proc = runcmd(cmd)
        lines = repo_list_proc.stdout.decode().strip().split('\n')
        for line in lines:
            (arch, pkg_path) = line.split('|')
            # check architecture matches
            if arch != self.archmap.native(architecture):
                continue
            return Path(pkg_path)
        raise RuntimeError(
            f"Unable to find deb path for deb binary package {bin_artifact}"
        )

    def _debian_archive_path(self, dsc_path):
        """Parses the given dsc file and returns the path of the archive
        containing the debian packaging code."""
        with open(dsc_path) as dsc_fh:
            dsc = deb822.Dsc(dsc_fh)
        for arch in dsc['Files']:
            if '.orig.' in arch['name']:  # skip orig archive
                continue
            return dsc_path.parent.joinpath(arch['name'])
        raise RuntimeError(
            "Unable to define debian archive path in deb dsc "
            f"file {dsc_path}"
        )

    def _extract_archive_changelog(self, arch_path):
        """Returns the content of the debian changelog file of the given
        archive file."""
        logger.debug("Extracting debian changelog from archive %s", arch_path)
        try:
            archive = tarfile.open(arch_path)
        except tarfile.TarError as err:
            raise RuntimeError(f"Unable to read archive {arch_path}: {err}")
        logger.debug("Files in archives: %s", archive.getnames())
        if 'debian/changelog' in archive.getnames():
            fobj = archive.extractfile('debian/changelog')
            return fobj.read()
        raise RuntimeError(
            f"Unable to find debian changelog file in archive {arch_path}"
        )

    def source_changelog(self, distribution, derivative, src_artifact):
        """Returns the content of the given deb source package changelog file
        as bytes."""
        dsc_path = self._package_dsc_path(
            distribution, derivative, src_artifact
        )
        arch_path = self._debian_archive_path(dsc_path)
        return self._extract_archive_changelog(arch_path)

    def _src_changelog(self, distribution, derivative, src_artifact):
        """Returns the list of ChangelogEntry of the given deb source package."""
        return DebChangelog(
            self.source_changelog(distribution, derivative, src_artifact)
        ).entries()

    def _bin_changelog(
        self, distribution, derivative, architecture, bin_artifact
    ):
        """Returns the changelog of a deb binary package."""
        deb_path = self._package_deb_path(
            distribution, derivative, architecture, bin_artifact
        )
        return DebChangelog(debfile.DebFile(deb_path).changelog()).entries()

    def changelog(self, distribution, derivative, architecture, artifact):
        if architecture == 'src':
            return self._src_changelog(distribution, derivative, artifact)
        else:
            return self._bin_changelog(
                distribution, derivative, architecture, artifact
            )

    def delete_artifact(self, distribution, derivative, artifact):

        # load the keyring agent
        self.instance.keyring.load_agent()

        if artifact.architecture == 'noarch':
            # If the architecture is noarch (ie. binary architecture
            # independant package), the package is duplicated in all
            # architectures on the deb repository. We must explicitely ask
            # reprepro to remove the package from all architectures.
            _archs = '|'.join(
                [
                    self.archmap.native(arch)
                    for arch in self.instance.pipelines.architectures
                ]
            )
        else:
            _archs = self.archmap.native(artifact.architecture)

        cmd = [
            'reprepro',
            '--basedir',
            self.path,
            '--component',
            derivative,
            '--architecture',
            _archs,
            'remove',
            distribution,
            artifact.name,
        ]
        proc = runcmd(
            cmd, env={'GNUPGHOME': str(self.instance.keyring.homedir)}
        )


class DebChangelog(changelog.Changelog):
    def __init__(self, fileobjorchangelog):
        if isinstance(fileobjorchangelog, changelog.Changelog):
            super().__init__()  # initialize parent w/o parsing
            self._blocks = fileobjorchangelog._blocks  # inject blocks in parent
        else:
            super().__init__(fileobjorchangelog)  # parse fileobj

    def entries(self):
        result = []
        for entry in self:
            # parse RFC2822 date to get int timestamps since epoch
            try:
                date = int(
                    email.utils.parsedate_to_datetime(entry.date).timestamp()
                )
            except ValueError as err:
                logger.warning(
                    "Unable to parse debian changelog entry date %s",
                    entry.date,
                )
                date = 0
            # filter empty lines in entry changes
            changes = [
                DebChangelog._sanitize_entry(change)
                for change in entry.changes()
                if change.strip() != ""
            ]
            result.append(
                ChangelogEntry(
                    entry.version.full_version, entry.author, date, changes
                )
            )
        return result

    @staticmethod
    def _sanitize_entry(entry):
        entry = entry.strip()
        # remove leading asterisk if present
        if entry.startswith('* '):
            entry = entry[2:]
        return entry
