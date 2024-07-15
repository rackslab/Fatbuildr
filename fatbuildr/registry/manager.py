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

from .formats.deb import RegistryDeb
from .formats.rpm import RegistryRpm
from .formats.osi import RegistryOsi
from ..errors import FatbuildrRegistryError


class RegistryManager:

    _formats = {
        'deb': RegistryDeb,
        'rpm': RegistryRpm,
        'osi': RegistryOsi,
    }

    def __init__(self, conf, instance):
        self.conf = conf
        self.instance = instance

    def formats(self):
        # return an empty list if the instance registry directory does not exist
        if not self.conf.dirs.registry.joinpath(self.instance.id).exists():
            return []

        return [
            item.name
            for item in self.conf.dirs.registry.joinpath(
                self.instance.id
            ).iterdir()
        ]

    def distributions(self, fmt):
        registry = self.factory(fmt)
        return registry.distributions

    def derivatives(self, fmt, distribution):
        registry = self.factory(fmt)
        return registry.derivatives(distribution)

    def artifacts(self, fmt, distribution, derivative):
        registry = self.factory(fmt)
        return registry.artifacts(distribution, derivative)

    def artifact_bins(self, fmt, distribution, derivative, src_artifact):
        registry = self.factory(fmt)
        return registry.artifact_bins(distribution, derivative, src_artifact)

    def artifact_src(self, fmt, distribution, derivative, bin_artifact):
        registry = self.factory(fmt)
        return registry.artifact_src(distribution, derivative, bin_artifact)

    def changelog(self, fmt, distribution, derivative, architecture, artifact):
        registry = self.factory(fmt)
        return registry.changelog(
            distribution, derivative, architecture, artifact
        )

    def artifact_content(
        self, fmt, distribution, derivative, architecture, artifact
    ):
        registry = self.factory(fmt)
        return registry.artifact_content(
            distribution, derivative, architecture, artifact
        )

    def delete_artifact(self, fmt, distribution, derivative, artifact):
        registry = self.factory(fmt)
        return registry.delete_artifact(distribution, derivative, artifact)

    def factory(self, fmt):
        """Instanciate the appropriate Registry for the given format."""
        if fmt not in RegistryManager._formats:
            raise FatbuildrRegistryError(
                f"Format {fmt} not supported by registries"
            )
        return RegistryManager._formats[fmt](self.conf, self.instance)
