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

import yaml

from .templates import Templeter
from .log import logr

logger = logr(__name__)


class ArtifactDefs:
    """Generic class to manipulate an artifact metadata definitions."""

    def __init__(self, place, artifact):
        self.place = place
        self.artifact = artifact
        meta_yml_f = place.joinpath('meta.yml')
        logger.debug("Loading artifact definitions from %s", meta_yml_f)
        with open(meta_yml_f) as fh:
            self.meta = yaml.safe_load(fh)

    @property
    def has_tarball(self):
        return 'tarball' in self.meta

    @property
    def supported_formats(self):
        return [
            key
            for key in self.meta.keys()
            if key not in ['version', 'versions', 'tarball', 'checksums']
        ]

    @property
    def derivatives(self):
        results = []
        if 'versions' in self.meta:
            results.extend(self.meta['versions'].keys())
        else:
            results.append('main')
        logger.debug("Supported derivatives: %s", results)
        return results

    def version(self, derivative):
        if derivative == 'main' and 'version' in self.meta:
            return str(self.meta['version'])
        else:
            return str(self.meta['versions'][derivative])

    def checksum_format(self, derivative):
        version = self.version(derivative)
        if version not in self.meta['checksums']:
            raise RuntimeError(
                f"Checksum of version {version} not found in artifact "
                "definition"
            )
        return list(self.meta['checksums'][self.version(derivative)].keys())[
            0
        ]  # pickup the first format

    def checksum_value(self, derivative):
        return self.meta['checksums'][self.version(derivative)][
            self.checksum_format(derivative)
        ]

    def tarball_url(self, version):
        tarball = Templeter().srender(self.meta['tarball'], version=version)
        if '!' in tarball:
            return tarball.split('!')[0]
        return tarball

    def tarball_filename(self, version):
        tarball = Templeter().srender(self.meta['tarball'], version=version)
        if '!' in tarball:
            return tarball.split('!')[1]
        return os.path.basename(tarball)

    @property
    def architecture_dependent(self):
        return False


class ArtifactFormatDefs(ArtifactDefs):
    def __init__(self, place, artifact, format):
        super().__init__(place, artifact)
        self.format = format

    @property
    def release(self):
        return str(self.meta[self.format]['release'])

    def fullversion(self, derivative):
        return self.version(derivative) + '-' + self.release


class ArtifactDebDefs(ArtifactFormatDefs):
    @property
    def architecture_dependent(self):
        """Returns true if the Debian source package is architecture dependent,
        or False otherwise.

        To determine the value, the Architecture parameter is checked for all
        declared binary packages. If at least one binary package is not
        'Architecture: all', the source package as a whole is considered
        architecture dependent."""
        check_file = self.place.joinpath(self.format, 'control')
        with open(check_file, 'r') as fh:
            for line in fh:
                if line.startswith('Architecture:') and not line.startswith(
                    'Architecture: all'
                ):
                    return True
        return False


class ArtifactRpmDefs(ArtifactFormatDefs):
    @property
    def architecture_dependent(self):
        """Returns true if the RPM source package is architecture dependent, or
        False otherwise.

        To determine the value, the BuildArch parameter is checked in RPM spec
        file. Unless BuildArch is set to noarch, the source package is
        considered architecture dependent."""
        check_file = self.place.joinpath(self.format, f"{self.artifact}.spec")
        with open(check_file, 'r') as fh:
            for line in fh:
                if (
                    line.replace(' ', '')
                    .replace('\t', '')
                    .startswith('BuildArch:noarch')
                ):
                    return False
        return True

    def has_buildargs(self, fmt):
        return 'buildargs' in self.meta[self.format]

    def buildargs(self, fmt):
        return self.meta[self.format]['buildargs'].split(' ')


class ArtifactOsiDefs(ArtifactDefs):
    pass


class ArtifactDefsFactory:

    _formats = {
        'deb': ArtifactDebDefs,
        'rpm': ArtifactRpmDefs,
        'osi': ArtifactOsiDefs,
    }

    @staticmethod
    def get(place, artifact, format):
        """Generate specialized ArtifactFormatDefs for the given format."""
        if not format in ArtifactDefsFactory._formats:
            raise RuntimeError(
                f"artifact definition format {format} is not supported"
            )
        return ArtifactDefsFactory._formats[format](place, artifact, format)
