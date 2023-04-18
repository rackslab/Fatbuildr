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
from .errors import FatbuildrArtifactError
from .log import logr

logger = logr(__name__)


class ArtifactSourceDefs:
    """Class to represent an artifact source."""

    def __init__(self, id, defs):
        self.id = id
        self.defs = defs

    @property
    def has_source(self):
        return 'source' in self.defs or (
            'sources' in self.defs and self.id in self.defs['sources']
        )

    @property
    def has_multisources(self):
        """True if multiple sources are defined in the same artifact definition
        file, False otherwise."""
        return 'sources' in self.defs

    @property
    def has_derivatives(self):
        """True if derivatives are defined in the artifact definition file,
        False otherwise."""
        return 'derivatives' in self.defs

    def is_main(self, artifact):
        return self.id == artifact

    def version(self, derivative):
        """Returns the version of the artifact source for the given
        derivative."""
        if self.has_derivatives:
            if self.has_multisources:
                try:
                    return str(
                        self.defs['derivatives'][derivative][self.id]['version']
                    )
                except KeyError:
                    raise FatbuildrArtifactError(
                        f"Unable to find version for source archive {self.id} "
                        f"for derivative {derivative} in YAML artifact "
                        "definition file"
                    )
            else:
                try:
                    return str(self.defs['derivatives'][derivative]['version'])
                except KeyError:
                    raise FatbuildrArtifactError(
                        f"Unable to find version for derivative {derivative} "
                        "in YAML artifact definition file"
                    )
        else:
            if self.has_multisources:
                try:
                    return str(self.defs['versions'][self.id])
                except KeyError:
                    raise FatbuildrArtifactError(
                        f"Unable to find version for source archive {self.id} "
                        "in YAML artifact definition file"
                    )
            else:
                try:
                    return str(self.defs['version'])
                except KeyError:
                    raise FatbuildrArtifactError(
                        "Unable to find version in YAML artifact definition "
                        "file"
                    )

    def checksums(self, derivative):
        """Returns a set of (algorithm, value) 2-tuples for all checksums
        defined for artifact source."""
        if self.has_multisources:
            checksums_dict = self.defs['checksums'][self.id][
                self.version(derivative)
            ]
        else:
            checksums_dict = self.defs['checksums'][self.version(derivative)]
        results = set()
        for algo, value in checksums_dict.items():
            results.add((algo, value))
        return results

    @property
    def _raw_source(self):
        if self.has_multisources:
            return self.defs['sources'][self.id]
        else:
            return self.defs['source']

    def url(self, derivative):
        """Returns the URL to download the artifact source for the given
        derivative."""
        url = Templeter().srender(
            self._raw_source, version=self.version(derivative)
        )
        if '!' in url:
            return url.split('!')[0]
        return url

    def filename(self, derivative):
        """Returns the filename of the artifact source for the given
        derivative."""
        url = Templeter().srender(
            self._raw_source, version=self.version(derivative)
        )
        if '!' in url:
            return url.split('!')[1]
        return os.path.basename(url)


class ArtifactDefs:
    """Generic class to manipulate a YAML artifact definition file."""

    SUPPORTED_FILENAMES = (
        ('artifact.yml', False),
        ('artifact.yaml', False),
        ('meta.yml', True),  # deprecated
    )

    def __init__(self, place, artifact):
        self.place = place
        self.artifact = artifact

        for filename in self.SUPPORTED_FILENAMES:
            defs_yml_f = place.joinpath(filename[0])
            if defs_yml_f.exists():
                if filename[1]:
                    logger.warn(
                        "Using deprecated filename %s as YAML artifact "
                        "definition file, please rename to %s",
                        filename[0],
                        self.SUPPORTED_FILENAMES[0][0],
                    )
                break

        if not defs_yml_f.exists():
            raise FatbuildrArtifactError(
                f"Unable to find artifact YAML definition file in path {place}/"
                '{'
                + ','.join(filename[0] for filename in self.SUPPORTED_FILENAMES)
                + '}'
            )

        logger.debug("Loading artifact definitions from %s", defs_yml_f)
        self.sources = list()
        with open(defs_yml_f) as fh:
            self.defs = yaml.safe_load(fh)
            if 'sources' in self.defs:
                for source_id, source_defs in self.defs['sources'].items():
                    self.sources.append(
                        ArtifactSourceDefs(source_id, self.defs)
                    )
            else:
                self.sources.append(
                    ArtifactSourceDefs(self.artifact, self.defs)
                )

    def source(self, id):
        for source in self.sources:
            if source.id == id:
                return source

    @property
    def main_source(self):
        return self.source(self.artifact)

    @property
    def defined_sources(self):
        """The list of source IDs defined in YAML artifact definition file."""
        return [source.id for source in self.sources]

    @property
    def derivatives(self):
        results = []
        if 'derivatives' in self.defs:
            results.extend(self.defs['derivatives'].keys())
        else:
            results.append('main')
        logger.debug("Supported derivatives: %s", results)
        return results

    @property
    def supported_formats(self):
        return [key for key in self.defs.keys() if key in ['rpm', 'deb', 'osi']]

    @property
    def architecture_dependent(self):
        return False


class ArtifactFormatDefs(ArtifactDefs):
    def __init__(self, place, artifact, format):
        super().__init__(place, artifact)
        self.format = format

    @property
    def release(self):
        return str(self.defs[self.format]['release'])

    def fullversion(self, derivative):
        return (
            self.source(self.artifact).version(derivative) + '-' + self.release
        )


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
        if not check_file.exists():
            check_file = check_file.with_suffix('.j2')
        if not check_file.exists():
            raise RuntimeError(
                "Unable to find deb package control file in directory %s",
                check_file.parent,
            )
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

    @property
    def has_buildargs(self):
        return 'buildargs' in self.defs[self.format]

    @property
    def buildargs(self):
        return self.defs[self.format]['buildargs'].split(' ')


class ArtifactOsiDefs(ArtifactDefs):
    @property
    def release(self):
        """The release number is not expected in definition file for osi format,
        then return hard-coded default value 0."""
        return 0


class ArtifactDefsFactory:

    _formats = {
        'deb': ArtifactDebDefs,
        'rpm': ArtifactRpmDefs,
        'osi': ArtifactOsiDefs,
    }

    @staticmethod
    def get(place, artifact, format):
        """Generate specialized ArtifactFormatDefs for the given format."""
        if format not in ArtifactDefsFactory._formats:
            raise RuntimeError(
                f"artifact definition format {format} is not supported"
            )
        return ArtifactDefsFactory._formats[format](place, artifact, format)
