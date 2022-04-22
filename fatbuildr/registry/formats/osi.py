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

import shutil
import re

from . import Registry, RegistryArtifact
from ...log import logr

logger = logr(__name__)


class RegistryOsi(Registry):
    """Registry for Osi format (aka. OS images)."""

    CHECKSUMS_FILES = ['SHA256SUMS', 'SHA256SUMS.gpg']

    def __init__(self, conf, instance):
        super().__init__(conf, instance, 'osi')

    @property
    def distributions(self):
        return [item.name for item in self.path.iterdir()]

    def derivatives(self, distribution):
        return [
            item.name for item in self.path.joinpath(distribution).iterdir()
        ]

    def derivative_path(self, distribution, derivative):
        return self.path.joinpath(distribution, derivative)

    def publish(self, build):
        """Publish OSI images."""

        logger.info("Publishing OSI images for %s", build.artifact)

        derivative_path = self.derivative_path(
            build.distribution, build.derivative
        )
        dist_path = derivative_path.parent
        registry_path = dist_path.parent

        # ensure registry (ie. osi) directory exists
        RegistryOsi.ensure_directory(registry_path)
        RegistryOsi.ensure_directory(dist_path)
        RegistryOsi.ensure_directory(derivative_path)

        built_files = [
            build.place.joinpath(_path) for _path in RegistryOsi.CHECKSUMS_FILES
        ]
        built_files.extend([_path for _path in build.place.glob('*.tar.*')])
        logger.debug("Found files: %s", ' '.join(built_files.name))

        for src in built_files:
            dst = derivative_path.joinpath(fpath)
            logger.debug("Copying file %s to %s", src, dst)
            shutil.copyfile(src, dst)

    def _artifacts_filter(self, distribution, derivative, name_filter=None):
        artifacts = []
        for _path in self.derivative_path(distribution, derivative).iterdir():
            if _path.name in RegistryOsi.CHECKSUMS_FILES:
                continue
            if _path.suffix == '.manifest':
                continue
            f_re = re.match(
                r'(?P<name>.+)_(?P<version>\d+)\.(?P<arch>.+)', _path.name
            )
            if not f_re:
                logger.warning(
                    "File %s does not match OSI artifact regular " "expression",
                    _path.name,
                )
                continue
            # skip if it does not match the filter
            if name_filter and f_re.group('name') != name_filter:
                continue
            artifacts.append(
                RegistryArtifact(
                    f_re.group('name'),
                    f_re.group('arch'),
                    f_re.group('version'),
                )
            )

        return artifacts

    def artifacts(self, distribution, derivative):
        """Returns the list of artifacts in OSI registry."""
        return self._artifacts_filter(distribution, derivative)

    def artifact_bins(self, distribution, derivative, src_artifact):
        """There is no notion of source/binary artifact with OSI format. This
        return the artifact whose name is the given source artifact."""
        return self._artifacts_filter(
            distribution, derivative, name_filter=src_artifact
        )

    def artifact_src(self, distribution, derivative, bin_artifact):
        """There is no notion of source/binary artifact with OSI format. This
        return the artifact whose name is the given binary artifact."""
        return self._artifacts_filter(
            distribution, derivative, name_filter=bin_artifact
        )[0]

    def changelog(self, distribution, derivative, architecture, artifact):
        """Return empty array as there is notion of changelog with OSI."""
        return []

    def delete_artifact(self, distribution, derivative, artifact):
        path = self.derivative_path(distribution, derivative).joinpath(
            f"{artifact.name}_{artifact.version}.{artifact.architecture}"
        )
        # delete the image if found
        if path.exists():
            logger.info("Deleting OSI file %s", path)
            path.unlink()
        else:
            logger.warning("Unable to find OSI file %s", path)
        # delete the manifest if found
        manifest = path.with_suffix('.manifest')
        if manifest.exists():
            logger.info("Deleting OSI manifest file %s", manifest)
            manifest.unlink()
        else:
            logger.warning("Unable to find OSI manifest file %s", manifest)

    @staticmethod
    def ensure_directory(path):
        """Create a directory with 0755 mode if it does not exist."""
        if not path.exists():
            logger.info("Creating directory %s", path)
            path.mkdir()
            path.chmod(0o755)
