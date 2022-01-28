
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


class Registry:
    """Abstract Registry class, parent of all specific Registry classes."""

    def __init__(self, conf, instance):
        self.conf = conf
        self.instance_dir = os.path.join(conf.dirs.repos, instance)

    @property
    def distributions(self):
        raise NotImplementedError

    def publish(self, build):
        raise NotImplementedError

    def artefact(self, distributions):
        raise NotImplementedError


class RegistryArtefact:
    def __init__(self, name, architecture, version):
        self.name = name
        self.architecture = architecture
        self.version = version

