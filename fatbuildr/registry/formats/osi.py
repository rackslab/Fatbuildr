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
import shutil

from . import Registry, RegistryArtefact
from ...log import logr

logger = logr(__name__)


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
        """Returns the list of artefacts in OSI registry."""
        return self._artefacts_filter(distribution)

    def artefact_bins(self, distribution, src_artefact):
        """There is no notion of source/binary artefact with OSI format. This
           return the artefact whose name is the given source artefact."""
        return self._artefacts_filter(distribution, name_filter=src_artefact)

    def artefact_src(self, distribution, bin_artefact):
        """There is no notion of source/binary artefact with OSI format. This
           return the artefact whose name is the given binary artefact."""
        return self._artefacts_filter(distribution,
                                      name_filter=bin_artefact)[0]

    def changelog(self, distribution, architecture, artefact):
        """Return empty array as there is notion of changelog with OSI."""
        return []
