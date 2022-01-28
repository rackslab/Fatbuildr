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

from .formats.deb import RegistryDeb
from .formats.rpm import RegistryRpm
from .formats.osi import RegistryOsi


class RegistryManager:

    _formats = {
        'deb': RegistryDeb,
        'rpm': RegistryRpm,
        'osi': RegistryOsi,
    }

    def __init__(self, conf):
        self.conf = conf

    @property
    def instances(self):
        return os.listdir(self.conf.dirs.repos)

    def formats(self, instance):
        return os.listdir(os.path.join(self.conf.dirs.repos, instance))

    def distributions(self, instance, fmt):
        registry = RegistryManager.factory(fmt, self.conf, instance)
        return registry.distributions

    def artefacts(self, instance, fmt, distribution):
        registry = RegistryManager.factory(fmt, self.conf, instance)
        return registry.artefacts(distribution)

    def artefact_bins(self, instance, fmt, distribution, src_artefact):
        registry = RegistryManager.factory(fmt, self.conf, instance)
        return registry.artefact_bins(distribution, src_artefact)

    def artefact_src(self, instance, fmt, distribution, bin_artefact):
        registry = RegistryManager.factory(fmt, self.conf, instance)
        return registry.artefact_src(distribution, bin_artefact)

    def changelog(self, instance, fmt, distribution, architecture, artefact):
        registry = RegistryManager.factory(fmt, self.conf, instance)
        return registry.changelog(distribution, architecture, artefact)

    @staticmethod
    def factory(fmt, conf, instance):
        """Instanciate the appropriate Registry for the given format."""
        if not fmt in RegistryManager._formats:
            raise RuntimeError("format %s unsupported by registries" % (fmt))
        return RegistryManager._formats[fmt](conf, instance)
