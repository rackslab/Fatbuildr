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

import yaml

from .templates import Templeter
from .log import logr

logger = logr(__name__)


class ArtefactDefs:
    """Class to manipulate an artefact metadata definitions."""

    def __init__(self, path):
        meta_yml_f = path.joinpath('meta.yml')
        logger.debug("Loading artefact definitions from %s", meta_yml_f)
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
        return list(self.meta['checksums'][self.version(derivative)].keys())[
            0
        ]  # pickup the first format

    def checksum_value(self, derivative):
        return self.meta['checksums'][self.version(derivative)][
            self.checksum_format(derivative)
        ]

    def release(self, fmt):
        return str(self.meta[fmt]['release'])

    def fullversion(self, fmt, derivative):
        return self.version(derivative) + '-' + self.release(fmt)

    def tarball(self, version):
        return Templeter().srender(self.meta['tarball'], version=version)

    def has_buildargs(self, fmt):
        return 'buildargs' in self.meta[fmt]

    def buildargs(self, fmt):
        return self.meta[fmt]['buildargs'].split(' ')
