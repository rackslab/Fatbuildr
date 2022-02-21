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
import re

from . import Registry, RegistryArtefact
from ...log import logr

logger = logr(__name__)


class RegistryOsi(Registry):
    """Registry for Osi format (aka. OS images)."""

    CHECKSUMS_FILES = ['SHA256SUMS', 'SHA256SUMS.gpg']

    def __init__(self, conf, instance):
        super().__init__(conf, instance)

    @property
    def path(self):
        return os.path.join(self.instance_dir, 'osi')

    @property
    def distributions(self):
        return os.listdir(self.path)

    def derivatives(self, distribution):
        return os.listdir(os.path.join(self.path, distribution))

    def derivative_path(self, distribution, derivative):
        return os.path.join(self.path, distribution, derivative)

    def publish(self, build):
        """Publish OSI images."""

        logger.info("Publishing OSI images for %s", build.artefact)

        derivative_path = self.derivative_path(
            build.distribution, build.derivative
        )
        dist_path = os.path.dirname(derivative_path)
        registry_path = os.path.dirname(dist_path)

        # ensure registry (ie. osi) directory exists
        RegistryOsi.ensure_directory(registry_path)
        RegistryOsi.ensure_directory(dist_path)
        RegistryOsi.ensure_directory(derivative_path)

        built_files = RegistryOsi.CHECKSUMS_FILES
        images_files_path = os.path.join(build.place, '*.tar.*')
        built_files.extend(
            [os.path.basename(_path) for _path in glob.glob(images_files_path)]
        )
        logger.debug("Found files: %s" % (' '.join(built_files)))

        for fpath in built_files:
            src = os.path.join(build.place, fpath)
            dst = os.path.join(derivative_path, fpath)
            logger.debug("Copying file %s to %s" % (src, dst))
            shutil.copyfile(src, dst)

    def _artefacts_filter(self, distribution, derivative, name_filter=None):
        artefacts = []
        for _path in os.listdir(self.derivative_path(distribution, derivative)):
            if _path in RegistryOsi.CHECKSUMS_FILES:
                continue
            if _path.endswith('.manifest'):
                continue
            f_re = re.match(
                r'(?P<name>.+)_(?P<version>\d+)\.(?P<arch>.+)', _path
            )
            if not f_re:
                logger.warning(
                    "File %s does not match OSI artefact regular "
                    "expression" % (_path)
                )
                continue
            # skip if it does not match the filter
            if name_filter and f_re.group('name') != name_filter:
                continue
            artefacts.append(
                RegistryArtefact(
                    f_re.group('name'),
                    f_re.group('arch'),
                    f_re.group('version'),
                )
            )

        return artefacts

    def artefacts(self, distribution, derivative):
        """Returns the list of artefacts in OSI registry."""
        return self._artefacts_filter(distribution, derivative)

    def artefact_bins(self, distribution, derivative, src_artefact):
        """There is no notion of source/binary artefact with OSI format. This
        return the artefact whose name is the given source artefact."""
        return self._artefacts_filter(
            distribution, derivative, name_filter=src_artefact
        )

    def artefact_src(self, distribution, derivative, bin_artefact):
        """There is no notion of source/binary artefact with OSI format. This
        return the artefact whose name is the given binary artefact."""
        return self._artefacts_filter(
            distribution, derivative, name_filter=bin_artefact
        )[0]

    def changelog(self, distribution, derivative, architecture, artefact):
        """Return empty array as there is notion of changelog with OSI."""
        return []

    def delete_artefact(self, distribution, derivative, artefact):
        path = os.path.join(
            self.derivative_path(distribution, derivative),
            f"{artefact.name}_{artefact.version}.{artefact.architecture}",
        )
        # delete the image if found
        if os.path.exists(path):
            logger.info("Deleting OSI file %s", path)
            os.remove(path)
        else:
            logger.warning("Unable to find OSI file %s", path)
        # delete the manifest if found
        manifest = path + '.manifest'
        if os.path.exists(manifest):
            logger.info("Deleting OSI manifest file %s", manifest)
            os.remove(manifest)
        else:
            logger.warning("Unable to find OSI manifest file %s", manifest)

    @staticmethod
    def ensure_directory(path):
        """Create a directory with 0755 mode if it does not exist."""
        if not os.path.exists(path):
            logger.info("Creating directory %s" % (path))
            os.mkdir(path)
            os.chmod(path, 0o755)
