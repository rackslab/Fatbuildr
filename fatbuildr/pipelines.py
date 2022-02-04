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


class PipelinesDefs(object):
    """Class to manipulate the pipelines definitions of a base directory."""

    def __init__(self, path):
        self.path = path
        pipelines_yml_f = os.path.join(self.path, 'pipelines.yml')
        logger.debug(
            "Loading pipelines definitions from %s" % (pipelines_yml_f)
        )
        with open(pipelines_yml_f) as fh:
            self.defs = yaml.safe_load(fh)

    @property
    def name(self):
        return self.defs['name']

    @property
    def msg(self):
        return self.defs['msg']

    @property
    def gpg_name(self):
        return self.defs['gpg']['name']

    @property
    def gpg_email(self):
        return self.defs['gpg']['email']

    def dist_format(self, distribution):
        """Which format (ex: RPM) for this distribution? Raise RuntimeError if
        the format has not been found."""
        for format, dists in self.defs['formats'].items():
            if distribution in dists.keys():
                return format
        raise RuntimeError(
            "Unable to find format corresponding to "
            "distribution %s" % (distribution)
        )

    def dist_env(self, distribution):
        """Return the name of the build environment for the given
        distribution. Raise RuntimeError is the environment has not been
        found."""
        for format, dists in self.defs['formats'].items():
            if distribution in dists.keys():
                return dists[distribution]
        raise RuntimeError(
            "Unable to find environment corresponding "
            "to distribution %s" % (distribution)
        )

    def format_dists(self, format):
        """Return the list of distributions for the given format."""
        return list(self.defs['formats'][format].keys())

    def derivative_formats(self, derivative):
        """Returns a set of formats supported by the derivative, proceeding
        recursively with derivatives extensions."""
        if derivative == 'main':
            _formats = set(self.defs['formats'].keys())
        else:
            _formats = set()
            if 'formats' in self.defs['derivatives'][derivative]:
                _formats = set(self.defs['derivatives'][derivative]['formats'])
            if 'extends' in self.defs['derivatives'][derivative]:
                _formats = _formats.intersection(
                    self.derivative_formats(
                        self.defs['derivatives'][derivative]['extends']
                    )
                )
            else:
                _formats = _formats.intersection(
                    self.derivative_formats('main')
                )
        logger.debug(
            "List of formats supported by derivative %s: %s",
            derivative,
            _formats,
        )
        return _formats

    def recursive_derivatives(self, derivative):
        """Returns the list of derivatives recursively extended by the given
        derivative."""
        if derivative == 'main':
            return ['main']
        if 'extends' in self.defs['derivatives'][derivative]:
            return [derivative] + self.recursive_derivatives(
                self.defs['derivatives'][derivative]['extends']
            )
        else:
            return [derivative] + self.recursive_derivatives('main')


class ArtefactDefs(object):
    """Class to manipulate an artefact metadata definitions."""

    def __init__(self, path):
        meta_yml_f = os.path.join(path, 'meta.yml')
        logger.debug("Loading artefact definitions from %s" % (meta_yml_f))
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
        if 'version' in self.meta:
            results.append('main')
        if 'versions' in self.meta:
            results.extend(self.meta['versions'].keys())
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

    def tarball(self, obj):
        return Templeter.srender(self.meta['tarball'], pkg=obj)

    def has_buildargs(self, fmt):
        return 'buildargs' in self.meta[fmt]

    def buildargs(self, fmt):
        return self.meta[fmt]['buildargs'].split(' ')
