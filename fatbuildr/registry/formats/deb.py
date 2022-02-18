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

import os
import glob
import tarfile
import email

from debian import deb822, changelog, debfile

from . import Registry, RegistryArtefact, ChangelogEntry
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
        return os.path.join(self.instance_dir, 'deb')

    @property
    def distributions(self):
        dists_path = os.path.join(self.path, 'dists')
        if not os.path.exists(dists_path):
            return []
        return os.listdir(dists_path)

    @property
    def components(self):
        pool_path = os.path.join(self.path, 'pool')
        if not os.path.exists(pool_path):
            return []
        return os.listdir(pool_path)

    def derivatives(self, distribution):
        return self.components

    def publish(self, build):
        """Publish both source and binary package in APT repository."""

        logger.info(
            "Publishing Deb packages for %s in distribution %s"
            % (build.name, build.distribution)
        )

        # load reprepro distributions template
        dists_tpl_path = os.path.join(
            self.conf.registry.conf, 'apt', 'distributions.j2'
        )
        dists_path = os.path.join(self.path, 'conf', 'distributions')

        # create parent directory recursively, if not present
        if not os.path.exists(os.path.dirname(dists_path)):
            os.makedirs(os.path.dirname(dists_path))

        # generate reprepro distributions file
        logger.debug("Generating distribution file %s" % (dists_path))
        # Combine existing distributions in repository with build distribution
        # to define resulting list of distributions.
        distributions = list(set(self.distributions + [build.distribution]))
        components = list(set(self.components + build.derivatives))
        with open(dists_path, 'w+') as fh:
            fh.write(
                Templeter.frender(
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
            "Checking if package %s is already present in "
            "distribution %s" % (build.name, build.distribution)
        )
        cmd = [
            'reprepro',
            '--basedir',
            self.path,
            '--list-format',
            '${version}',
            'list',
            build.distribution,
            build.name,
        ]
        # build.runcmd() is not used here because we want to capture and parse
        # output here, and it writes the output to the build log file.
        repo_list = runcmd(cmd)

        if repo_list.stdout.decode() == build.fullversion:
            raise RuntimeError(
                "package %s already present in distribution %s "
                "with version %s"
                % (build.name, build.distribution, build.fullversion)
            )

        changes_glob = os.path.join(build.place, '*.changes')
        for changes_path in glob.glob(changes_glob):
            # Skip source changes, source package is published in repository as
            # part of binary changes.
            if changes_path.endswith('_source.changes'):
                continue
            logger.debug("Publishing deb changes file %s" % (changes_path))
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
            build.runcmd(cmd, env={'GNUPGHOME': self.instance.keyring.homedir})

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
        """Returns the list of binary deb packages generated by the given source
        deb package."""
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
            return pkg_path
        raise RuntimeError(
            "Unable to find dsc path for deb source package " f"{src_artefact}"
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
            return pkg_path
        raise RuntimeError(
            "Unable to find deb path for deb binary package " f"{bin_artefact}"
        )

    def _debian_archive_path(self, dsc_path):
        """Parses the given dsc file and returns the path of the archive
        containing the debian packaging code."""
        with open(dsc_path) as dsc_fh:
            dsc = deb822.Dsc(dsc_fh)
        for arch in dsc['Files']:
            if '.orig.' in arch['name']:  # skip orig archive
                continue
            return os.path.join(os.path.dirname(dsc_path), arch['name'])
        raise RuntimeError(
            "Unable to define debian archive path in deb dsc "
            f"file {dsc_path}"
        )

    def _extract_archive_changelog(self, arch_path):
        logger.debug("Extracting debian changelog from archive %s", arch_path)
        try:
            archive = tarfile.open(arch_path)
        except tarfile.TarError as err:
            raise RuntimeError(f"Unable to read archive {arch_path}: {err}")
        logger.debug("Files in archives: %s", archive.getnames())
        if 'debian/changelog' in archive.getnames():
            fobj = archive.extractfile('debian/changelog')
            return DebChangelog(fobj.read())
        raise RuntimeError(
            "Unable to find debian changelog file in archive " f"{arch_path}"
        )

    def _src_changelog(self, distribution, derivative, src_artefact):
        """Returns the changelog of a deb source package."""
        dsc_path = self._package_dsc_path(
            distribution, derivative, src_artefact
        )
        arch_path = self._debian_archive_path(dsc_path)
        return self._extract_archive_changelog(arch_path).entries()

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
        proc = runcmd(cmd, env={'GNUPGHOME': self.instance.keyring.homedir})

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
                    "Unable to parse debian changelog entry date " "%s",
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
