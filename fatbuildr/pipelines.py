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
import logging

logger = logging.getLogger(__name__)


class PipelinesDefs():
    """Class to manipulate the pipelines definitions of a base directory."""

    def __init__(self, path):
        self.path = path
        dists_yml_f = os.path.join(self.path, 'pipelines.yml')
        logger.debug("Loading pipelines definitions from %s" % (dists_yml_f))
        with open(dists_yml_f) as fh:
            self.dists = yaml.safe_load(fh)

    @property
    def gpg_name(self):
        return self.dists['gpg']['name']

    @property
    def gpg_email(self):
        return self.dists['gpg']['email']

    def dist_format(self, distribution):
        """Which format (ex: RPM) for this distribution? Returns None if
           distribution has not been found."""
        for format, dists in self.dists.items():
            if distribution in dists.keys():
                return format
        return None

    def dist_env(self, distribution):
        """Return the name of the build environment for the given
           distribution."""
        for format, dists in self.dists.items():
            if distribution in dists.keys():
                return dists[distribution]
        return None

    def format_dists(self, format):
        """Return the list of distributions for the given format."""
        return self.dists[format].keys()
