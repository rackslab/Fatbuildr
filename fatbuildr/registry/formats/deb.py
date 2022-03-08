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

from . import Registry, ArtefactVersion, RegistryArtefact, ChangelogEntry
from ...templates import Templeter
from ...utils import runcmd
from ...log import logr

logger = logr(__name__)


class RegistryDeb(Registry):
    """Registry for Deb format (aka. APT repository)."""

    ARCH_MAP = [('src', 'source')]

    def __init__(self, conf, instance):
        super().__init__(conf, instance)

    @property
    def path(self):
        return self.instance_dir.joinpath('deb')

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

    def derivatives(self, distribution):
        return self.components

    def publish(self, build):
        """Publish both source and binary package in APT repository."""

        logger.info(
            "Publishing Deb packages for %s in distribution %s",
            build.artefact,
            build.distribution,
        )

        # load reprepro distributions template
        dists_tpl_path = self.conf.registry.conf.joinpath(
            'apt', 'distributions.j2'
        )
        dists_path = self.path.joinpath('conf', 'distributions')

        # create parent directory recursively, if not present
        if not dists_path.parent.exists():
            dists_path.parent.mkdir(parents=True)

        # generate reprepro distributions file
        logger.debug("Generating distribution file %s", dists_path)
        # Combine existing distributions in repository with build distribution
        # to define resulting list of distributions.
        distributions = list(set(self.distributions + [build.distribution]))
        components = list(set(self.components + build.derivatives))
        with open(dists_path, 'w+') as fh:
            fh.write(
                Templeter().frender(
                    dists_tpl_path,
                    distributions=distributions,
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
            build.artefact,
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
            build.artefact,
        ]
        # build.runcmd() is not used here because we want to capture and parse
        # output here, and it writes the output to the build log file.
        repo_list = runcmd(cmd)

        if repo_list.stdout.decode() == build.fullversion:
            raise RuntimeError(
                f"package {build.artefact} already present in distribution "
                f"{build.distribution} with version {build.version.full}",
            )

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

    def artefacts(self, distribution, derivative):
        """Returns the list of artefacts in deb repository."""
        artefacts = []
        cmd = [
            'reprepro',
            '--basedir',
            self.path,
            '--component',
            derivative,
            '--list-format',
            '${package}|${$architecture}|${version}\n',
            'list',
            distribution,
        ]
        repo_list_proc = runcmd(cmd)
        lines = repo_list_proc.stdout.decode().strip().split('\n')
        for line in lines:
            if not line:
                continue
            (name, arch, version) = line.split('|')
            artefacts.append(
                RegistryArtefact(name, RegistryDeb.fatarch(arch), version)
            )
        return artefacts

    def artefact_bins(self, distribution, derivative, src_artefact):
        """Returns the list of binary deb packages generated by the given source
        deb package."""
        artefacts = []
        cmd = [
            'reprepro',
            '--basedir',
            self.path,
            '--component',
            derivative,
            '--list-format',
            '${package}|${$architecture}|${$source}|${version}\n',
            'list',
            distribution,
        ]
        repo_list_proc = runcmd(cmd)
        lines = repo_list_proc.stdout.decode().strip().split('\n')
        for line in lines:
            (name, arch, source, version) = line.split('|')
            if arch == 'source':  # skip non-binary package
                continue
            if source != src_artefact:
                continue
            artefacts.append(RegistryArtefact(name, arch, version))
        return artefacts

    def artefact_src(self, distribution, derivative, bin_artefact):
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
            bin_artefact,
        ]
        repo_list_proc = runcmd(cmd)
        lines = repo_list_proc.stdout.decode().strip().split('\n')
        for line in lines:
            (arch, source, version) = line.split('|')
            if arch == 'source':  # skip source package
                continue
            return RegistryArtefact(source, 'src', version)

    def source_version(self, distribution, derivative, artefact):
        """Returns the version of the given source package name, or None if not
        found."""
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
            artefact,
        ]
        repo_list_proc = runcmd(cmd)
        lines = repo_list_proc.stdout.decode().strip().split('\n')
        for line in lines:
            if not line:
                continue
            (arch, version) = line.split('|')
            if arch != 'source':  # skip binary package
                continue
            return ArtefactVersion(version)
        return None

    def _package_dsc_path(self, distribution, derivative, src_artefact):
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
            src_artefact,
        ]
        repo_list_proc = runcmd(cmd)
        lines = repo_list_proc.stdout.decode().strip().split('\n')
        for line in lines:
            (arch, pkg_path) = line.split('|')
            if arch != 'source':  # skip binary package
                continue
            return Path(pkg_path)
        raise RuntimeError(
            f"Unable to find dsc path for deb source package {src_artefact}"
        )

    def _package_deb_path(
        self, distribution, derivative, architecture, bin_artefact
    ):
        """Returns the path to the deb file of the given deb binary package."""
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
            bin_artefact,
        ]
        repo_list_proc = runcmd(cmd)
        lines = repo_list_proc.stdout.decode().strip().split('\n')
        for line in lines:
            (arch, pkg_path) = line.split('|')
            if arch != architecture:  # skip binary package
                continue
            return Path(pkg_path)
        raise RuntimeError(
            f"Unable to find deb path for deb binary package {bin_artefact}"
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

    def source_changelog(self, distribution, derivative, src_artefact):
        """Returns the content of the given deb source package changelog file
        as bytes."""
        dsc_path = self._package_dsc_path(
            distribution, derivative, src_artefact
        )
        arch_path = self._debian_archive_path(dsc_path)
        return self._extract_archive_changelog(arch_path)

    def _src_changelog(self, distribution, derivative, src_artefact):
        """Returns the list of ChangelogEntry of the given deb source package."""
        return DebChangelog(
            self.source_changelog(distribution, derivative, src_artefact)
        ).entries()

    def _bin_changelog(
        self, distribution, derivative, architecture, bin_artefact
    ):
        """Returns the changelog of a deb binary package."""
        deb_path = self._package_deb_path(
            distribution, derivative, architecture, bin_artefact
        )
        return DebChangelog(debfile.DebFile(deb_path).changelog()).entries()

    def changelog(self, distribution, derivative, architecture, artefact):
        if architecture == 'src':
            return self._src_changelog(distribution, derivative, artefact)
        else:
            return self._bin_changelog(
                distribution, derivative, architecture, artefact
            )

    def delete_artefact(self, distribution, derivative, artefact):

        # load the keyring agent
        self.instance.keyring.load_agent()

        cmd = [
            'reprepro',
            '--basedir',
            self.path,
            '--component',
            derivative,
            '--architecture',
            RegistryDeb.debarch(artefact.architecture),
            'remove',
            distribution,
            artefact.name,
        ]
        proc = runcmd(
            cmd, env={'GNUPGHOME': str(self.instance.keyring.homedir)}
        )

    @staticmethod
    def debarch(arch):
        for fatarch, debarch in RegistryDeb.ARCH_MAP:
            if arch == fatarch:
                return debarch
        return arch

    @staticmethod
    def fatarch(arch):
        for fatarch, debarch in RegistryDeb.ARCH_MAP:
            if arch == debarch:
                return fatarch
        return arch


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
