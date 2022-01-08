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
import shutil
import logging

from .keyring import KeyringManager
from .templates import Templeter

logger = logging.getLogger(__name__)


class Registry(object):
    """Abstract Registry class, parent of all specific Registry classes."""

    def __init__(self, conf, distribution):
        self.conf = conf
        self.instance_dir = os.path.join(conf.dirs.repos, conf.run.instance)
        self.distribution = distribution

    def publish(self, build):
        raise NotImplementedError


class RegistryDeb(Registry):
    """Registry for Deb format (aka. APT repository)."""

    def __init__(self, conf, distribution):
        super().__init__(conf, distribution)
        self.keyring = KeyringManager(conf)
        self.keyring.load()

    @property
    def path(self):
        return os.path.join(self.instance_dir, 'deb')

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
        with open(dists_path, 'w+') as fh:
            fh.write(Templeter.frender(dists_tpl_path,
                       distributions=[build.distribution],
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

        changes_glob = os.path.join(build.tmpdir, '*.changes')
        for changes_path in glob.glob(changes_glob):
            # Skip source changes, source package is published in repository as
            # part of binary changes.
            if changes_path.endswith('_source.changes'):
                continue
            logger.debug("Publishing deb changes file %s" % (changes_path))
            cmd = ['reprepro', '--verbose', '--basedir', self.path,
                   'include', build.distribution, changes_path ]
            logger.debug("run cmd: %s" % (' '.join(cmd)))
            subprocess.run(cmd, env={'GNUPGHOME': self.keyring.homedir})


class RegistryRpm(Registry):
    """Registry for Rpm format (aka. yum/dnf repository)."""

    def __init__(self, conf, distribution):
        super().__init__(conf, distribution)

    @property
    def path(self):
        return os.path.join(self.instance_dir, 'rpm', self.distribution)

    @property
    def pkg_dir(self):
        return os.path.join(self.path, 'Packages')

    def _mk_missing_repo_dirs(self):
        """Create pkg_dir if it does not exists, considering pkg_dir is a
           subdirectory of repo_dir."""
        if not os.path.exists(self.pkg_dir):
            logger.info("Creating missing package directory %s" \
                        % (self.pkg_dir))
            os.makedirs(self.pkg_dir)

    def publish(self, build):
        """Publish RPM (including SRPM) in yum/dnf repository."""

        logger.info("Publishing RPM packages for %s in distribution %s" \
                    % (build.name, build.distribution))

        self._mk_missing_repo_dirs()

        rpm_glob = os.path.join(build.tmpdir, '*.rpm')
        for rpm_path in glob.glob(rpm_glob):
            logger.debug("Copying RPM %s to %s" % (rpm_path, self.pkg_dir))
            shutil.copy(rpm_path, self.pkg_dir)

        logger.debug("Updating metadata of RPM repository %s" % (self.path))
        cmd = [ 'createrepo_c', '--update', self.path ]
        logger.debug("run cmd: %s" % (' '.join(cmd)))
        subprocess.run(cmd)
