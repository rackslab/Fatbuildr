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

from pathlib import Path

import yaml

from .tasks.manager import ServerTasksManager
from .registry.manager import RegistryManager
from .archives import ArchivesManager

from .utils import Singleton
from .log import logr

logger = logr(__name__)


class InstancePipelines:
    """Class to manipulate instance pipelines."""

    def __init__(self, formats, derivatives):
        self._formats = formats
        self.derivatives = derivatives

    @property
    def formats(self):
        return list(self._formats.keys())

    def dist_format(self, distribution):
        """Which format (ex: RPM) for this distribution? Raise RuntimeError if
        the format has not been found."""
        for format, dists in self._formats.items():
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
        for format, dists in self._formats.items():
            if distribution in dists.keys():
                return dists[distribution]
        raise RuntimeError(
            "Unable to find environment corresponding "
            "to distribution %s" % (distribution)
        )

    def dist_derivatives(self, distribution):
        """Return the list of derivatives for the given distribution."""
        result = ['main']
        if not self.derivatives:
            return result
        # get the format of the distribution to find the associated derivatives
        format = self.dist_format(distribution)
        for derivative, items in self.derivatives.items():
            if 'formats' in items and format in items['formats']:
                result.append(derivative)
        return result

    def format_dists(self, format):
        """Return the list of distributions for the given format."""
        return list(self._formats[format].keys())

    def derivative_formats(self, derivative):
        """Returns a set of formats supported by the derivative, proceeding
        recursively with derivatives extensions."""
        if derivative == 'main':
            _formats = set(self.formats)
        else:
            _formats = set()
            if 'formats' in self.derivatives[derivative]:
                _formats = set(self.derivatives[derivative]['formats'])
            if 'extends' in self.derivatives[derivative]:
                _formats = _formats.intersection(
                    self.derivative_formats(
                        self.derivatives[derivative]['extends']
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
        if 'extends' in self.derivatives[derivative]:
            return [derivative] + self.recursive_derivatives(
                self.derivatives[derivative]['extends']
            )
        else:
            return [derivative] + self.recursive_derivatives('main')


class RunningInstance:
    def __init__(self, conf, id, name, gpg_name, gpg_email, pipelines):
        self.conf = conf
        self.id = id
        self.name = name
        self.gpg_name = gpg_name
        self.gpg_email = gpg_email
        self.pipelines = pipelines
        self.tasks_mgr = ServerTasksManager(self.conf, self)
        self.registry_mgr = RegistryManager(self.conf, self)
        self.archives_mgr = ArchivesManager(self.conf, self)

    @property
    def userid(self):
        return f"{self.gpg_name} <{self.gpg_email}>"

    @classmethod
    def load(cls, conf, path):
        logger.debug("Loading instances definitions from %s" % (path))
        with open(path) as fh:
            defs = yaml.safe_load(fh)
        derivatives = None
        if 'derivatives' in defs:
            derivatives = defs['derivatives']
        pipelines = InstancePipelines(defs['formats'], derivatives)
        return cls(
            conf,
            path.stem,
            defs['name'],
            defs['gpg']['name'],
            defs['gpg']['email'],
            pipelines,
        )


class Instances(metaclass=Singleton):
    """Manages the instances definitions in dedicated directory"""

    def __init__(self, conf):
        self.conf = conf
        self.dir = Path(conf.dirs.instances)
        self._instances = {}

    def load(self):
        """Load all instances from definition files."""
        for instance_path in self.dir.glob("*.yml"):
            logger.info("Loading settings of instance %s", instance_path.stem)
            self._instances[instance_path.stem] = RunningInstance.load(
                self.conf, instance_path
            )
        logger.info("All instances are loaded")

    def __getitem__(self, instance):
        return self._instances[instance]

    def __iter__(self):
        for value in self._instances.values():
            yield value
