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
import subprocess
import glob

from . import Registry, RegistryArtefact
from ...keyring import KeyringManager
from ...templates import Templeter
from ...log import logr

logger = logr(__name__)


class RegistryDeb(Registry):
    """Registry for Deb format (aka. APT repository)."""

    def __init__(self, conf, instance):
        super().__init__(conf, instance)
        self.keyring = KeyringManager(conf, instance)
        self.keyring.load()

    @property
    def path(self):
        return os.path.join(self.instance_dir, 'deb')

    @property
    def distributions(self):
        return os.listdir(os.path.join(self.path, 'dists'))

    def publish(self, build):
        """Publish both source and binary package in APT repository."""

        logger.info("Publishing Deb packages for %s in distribution %s" \
                    % (build.name, build.distribution))

        # load reprepro distributions template
        dists_tpl_path = os.path.join(self.conf.registry.conf,
                                      'apt', 'distributions.j2')
        dists_path = os.path.join(self.path, 'conf', 'distributions')

        # create parent directory recursively, if not present
        if not os.path.exists(os.path.dirname(dists_path)):
            os.makedirs(os.path.dirname(dists_path))

        # generate reprepro distributions file
        logger.debug("Generating distribution file %s" % (dists_path))
        # Combine existing distributions in repository with build distribution
        # to define resulting list of distributions.
        distributions = list(set(self.distributions + [build.distribution]))
        with open(dists_path, 'w+') as fh:
            fh.write(Templeter.frender(dists_tpl_path,
                       distributions=distributions,
                       key=self.keyring.masterkey.subkey.fingerprint,
                       instance=build.source))

        # Load keyring in agent so repos are signed with new packages
        self.keyring.load_agent()

        # Check packages are not already present in this distribution of the
        # repository with this version before trying to publish them, or fail
        # when it is the case.
        logger.debug("Checking if package %s is already present in "
                     "distribution %s" % (build.name, build.distribution))
        cmd = ['reprepro', '--basedir', self.path,
               '--list-format', '${version}',
               'list', build.distribution, build.name ]
        logger.debug("run cmd: %s" % (' '.join(cmd)))
        repo_list = subprocess.run(cmd, capture_output=True)

        if repo_list.stdout.decode() == build.fullversion:
            raise RuntimeError("package %s already present in distribution %s "
                               "with version %s" \
                               % (build.name,
                                  build.distribution,
                                  build.fullversion))

        changes_glob = os.path.join(build.place, '*.changes')
        for changes_path in glob.glob(changes_glob):
            # Skip source changes, source package is published in repository as
            # part of binary changes.
            if changes_path.endswith('_source.changes'):
                continue
            logger.debug("Publishing deb changes file %s" % (changes_path))
            cmd = ['reprepro', '--verbose', '--basedir', self.path,
                   'include', build.distribution, changes_path ]
            build.runcmd(cmd, env={'GNUPGHOME': self.keyring.homedir})

    def artefacts(self, distribution):
        """Returns the list of artefacts in deb repository."""
        artefacts = []
        cmd = ['reprepro', '--basedir', self.path,
               '--list-format', '${package}|${$architecture}|${version}\n',
               'list', distribution ]
        repo_list_proc = subprocess.run(cmd, capture_output=True)
        lines = repo_list_proc.stdout.decode().strip().split('\n')
        for line in lines:
            (name, arch, version) = line.split('|')
            if arch == 'source':
                arch = 'src'
            artefacts.append(RegistryArtefact(name, arch, version))
        return artefacts

    def artefact_bins(self, distribution, src_artefact):
        """Returns the lost binary deb packages generated by the given source
           deb package."""
        artefacts = []
        cmd = ['reprepro', '--basedir', self.path,
               '--list-format',
               '${package}|${$architecture}|${$source}|${version}\n',
               'list', distribution ]
        repo_list_proc = subprocess.run(cmd, capture_output=True)
        lines = repo_list_proc.stdout.decode().strip().split('\n')
        for line in lines:
            (name, arch, source, version) = line.split('|')
            if arch == 'source':  # skip non-binary package
                continue
            if source != src_artefact:
                continue
            artefacts.append(RegistryArtefact(name, arch, version))
        return artefacts

    def artefact_src(self, distribution, bin_artefact):
        """Returns the lost binary deb packages generated by the given source
           deb package."""
        cmd = ['reprepro', '--basedir', self.path,
               '--list-format',
               '${$architecture}|${$source}|${version}\n',
               'list', distribution, bin_artefact ]
        repo_list_proc = subprocess.run(cmd, capture_output=True)
        lines = repo_list_proc.stdout.decode().strip().split('\n')
        for line in lines:
            (arch, source, version) = line.split('|')
            if arch == 'source':  # skip source package
                continue
            return RegistryArtefact(source, 'src', version)
