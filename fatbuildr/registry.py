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
import re

import createrepo_c as cr

from .keyring import KeyringManager
from .templates import Templeter
from .log import logr

logger = logr(__name__)


class Registry(object):
    """Abstract Registry class, parent of all specific Registry classes."""

    def __init__(self, conf, instance):
        self.conf = conf
        self.instance_dir = os.path.join(conf.dirs.repos, instance)

    @property
    def distributions(self):
        raise NotImplementedError

    def publish(self, build):
        raise NotImplementedError

    def artefact(self, distributions):
        raise NotImplementedError


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


class RegistryRpm(Registry):
    """Registry for Rpm format (aka. yum/dnf repository)."""

    def __init__(self, conf, instance):
        super().__init__(conf, instance)

    @property
    def distributions(self):
        return os.listdir(os.path.join(self.instance_dir, 'rpm'))

    def distribution_path(self, distribution):
        return os.path.join(self.instance_dir, 'rpm', distribution)

    def pkg_dir(self, distribution):
        return os.path.join(self.distribution_path(distribution), 'Packages')

    def _mk_missing_repo_dirs(self, distribution):
        """Create pkg_dir if it does not exists, considering pkg_dir is a
           subdirectory of repo_dir."""
        pkg_dir = self.pkg_dir(distribution)
        if not os.path.exists(pkg_dir):
            logger.info("Creating missing package directory %s" % (pkg_dir))
            os.makedirs(pkg_dir)

    def publish(self, build):
        """Publish RPM (including SRPM) in yum/dnf repository."""

        logger.info("Publishing RPM packages for %s in distribution %s" \
                    % (build.name, build.distribution))

        dist_path = self.distribution_path(distribution)
        pkg_dir = self.pkg_dir(distribution)

        self._mk_missing_repo_dirs(build.distribution)

        rpm_glob = os.path.join(build.place, '*.rpm')
        for rpm_path in glob.glob(rpm_glob):
            logger.debug("Copying RPM %s to %s" % (rpm_path, pkg_dir))
            shutil.copy(rpm_path, pkg_dir)

        logger.debug("Updating metadata of RPM repository %s" % (dist_path))
        cmd = ['createrepo_c', '--update', dist_path]
        build.runcmd(cmd)

    def artefacts(self, distribution):
        """Returns the list of artefacts in rpm repository."""
        artefacts = []
        md = cr.Metadata()
        md.locate_and_load_xml(self.distribution_path(distribution))
        for key in md.keys():
            pkg = md.get(key)
            artefacts.append(RegistryArtefact(pkg.name, pkg.arch,
                                              pkg.version+'-'+pkg.release))
        return artefacts

    def artefact_bins(self, distribution, src_artefact):
        """Returns the list of binary RPM generated by the given source RPM."""
        artefacts = []
        md = cr.Metadata()
        md.locate_and_load_xml(self.distribution_path(distribution))
        for key in md.keys():
            pkg = md.get(key)
            if pkg.arch == 'src':  # skip non-binary package
                continue
            # The createrepo_c library gives access to full the source RPM
            # filename, including its version and its extension. We must
            # extract the source package name out of this filename.
            source = pkg.rpm_sourcerpm.rsplit('-', 2)[0]
            if source != src_artefact:
                continue
            artefacts.append(RegistryArtefact(pkg.name, pkg.arch,
                                              pkg.version+'-'+pkg.release))
        return artefacts


class RegistryOsi(Registry):
    """Registry for Osi format (aka. OS images)."""

    CHECKSUMS_FILES =  ['SHA256SUMS', 'SHA256SUMS.gpg']

    def __init__(self, conf, instance):
        super().__init__(conf, instance)

    @property
    def distributions(self):
        return os.listdir(os.path.join(self.instance_dir, 'osi'))

    def distribution_path(self, distribution):
        return os.path.join(self.instance_dir, 'osi', distribution)

    def publish(self, build):
        """Publish OSI images."""

        logger.info("Publishing OSI images for %s" % (build.name))

        dist_path = self.distribution_path(build.distribution)

        # ensure osi directory exists
        parent = os.path.dirname(dist_path)
        if not os.path.exists(parent):
            logger.debug("Creating directory %s" % (parent))
            os.mkdir(parent)
            os.chmod(parent, 0o755)

        # ensure distribution directory exists
        if not os.path.exists(dist_path):
            logger.debug("Creating directory %s" % (dist_path))
            os.mkdir(dist_path)
            os.chmod(dist_path, 0o755)

        built_files = RegistryOsi.CHECKSUMS_FILES
        images_files_path = os.path.join(build.place, '*.tar.*')
        built_files.extend([os.path.basename(_path)
                            for _path in glob.glob(images_files_path)])
        logger.debug("Found files: %s" % (' '.join(built_files)))

        for fpath in built_files:
            src = os.path.join(build.place, fpath)
            dst = os.path.join(dist_path, fpath)
            logger.debug("Copying file %s to %s" % (src, dst))
            shutil.copyfile(src, dst)

    def _artefacts_filter(self, distribution, name_filter=None):
        artefacts = []
        for _path in os.listdir(self.distribution_path(distribution)):
            if _path in RegistryOsi.CHECKSUMS_FILES:
                continue
            if _path.endswith('.manifest'):
                continue
            f_re = re.match(r'(?P<name>.+)_(?P<version>\d+)\.(?P<arch>.+)',
                            _path)
            if not f_re:
                logger.warning("File %s does not match OSI artefact regular "
                               "expression" % (_path))
                continue
            # skip if it does not match the filter
            if name_filter and f_re.group('name') != name_filter:
                continue
            artefacts.append(RegistryArtefact(f_re.group('name'),
                                              f_re.group('arch'),
                                              f_re.group('version')))

        return artefacts

    def artefacts(self,  distribution):
        """Returns the list of artefacts in rpm repository."""
        return self._artefacts_filter(distribution)

    def artefact_bins(self, distribution, src_artefact):
        """There is no notion of source/binary artefact with OSI format. This
           return the artefact whose name is the given source artefact."""
        return self._artefacts_filter(distribution, name_filter=src_artefact)


class RegistryArtefact:
    def __init__(self, name, architecture, version):
        self.name = name
        self.architecture = architecture
        self.version = version


class RegistryFactory:
    _formats = {
        'deb': RegistryDeb,
        'rpm': RegistryRpm,
        'osi': RegistryOsi,
    }

    @staticmethod
    def get(fmt, conf, instance):
        """Instanciate the appropriate Registry for the given format."""
        if not fmt in RegistryFactory._formats:
            raise RuntimeError("format %s unsupported by registries" % (fmt))
        return RegistryFactory._formats[fmt](conf, instance)


class RegistryManager:

    FACTORY = RegistryFactory

    def __init__(self, conf):
        self.conf = conf

    @property
    def instances(self):
        return os.listdir(self.conf.dirs.repos)

    def formats(self, instance):
        return os.listdir(os.path.join(self.conf.dirs.repos, instance))

    def distributions(self, instance, fmt):
        registry = RegistryFactory.get(fmt, self.conf, instance)
        return registry.distributions

    def artefacts(self, instance, fmt, distribution):
        registry = RegistryFactory.get(fmt, self.conf, instance)
        return registry.artefacts(distribution)

    def artefact_bins(self, instance, fmt, distribution, src_artefact):
        registry = RegistryFactory.get(fmt, self.conf, instance)
        return registry.artefact_bins(distribution, src_artefact)
