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

import re

from ...specifics import ArchMap
from ...protocols.exports import ExportableType, ExportableField


class Registry:
    """Abstract Registry class, parent of all specific Registry classes."""

    def __init__(self, conf, instance, format):
        self.conf = conf
        self.instance = instance
        self.instance_dir = conf.dirs.registry.joinpath(instance.id)
        self.format = format
        self.archmap = ArchMap(format)

    @property
    def distributions(self):
        raise NotImplementedError

    @property
    def path(self):
        return self.instance_dir.joinpath(self.format)

    @property
    def exists(self):
        return self.path.exists()

    def publish(self, build):
        raise NotImplementedError

    def artifact(self, distributions):
        raise NotImplementedError


class ArtifactVersion:
    VERSION_REGEX = r'(?P<main>.+)-(?P<release>.+)'
    RELEASE_REGEX = (
        r'(?P<release>.+?)(\.(?P<dist>\w+))?(\+build(?P<build>\d+))?'
    )

    def __init__(self, value):
        version_re = re.match(self.VERSION_REGEX, value)
        if not version_re:
            raise RuntimeError(f"Unable to parse version {value}")
        self.main = version_re.group('main')
        release = version_re.group('release')
        release_re = re.match(self.RELEASE_REGEX, release)
        self.release = release_re.group('release')
        self.dist = release_re.group('dist')
        if release_re.group('build'):
            self.build = int(release_re.group('build'))
        else:
            self.build = -1

    def __eq__(self, other):
        """Compares two versions, without considering the build number."""
        return (
            self.main == other.main
            and self.release == other.release
            and self.dist == other.dist
        )

    @property
    def major(self):
        """Returns the first part of the main version as an integer"""
        return int(self.main.split('.')[0])

    @property
    def full(self):
        """Returns the full version as a string."""
        return f"{self.main}-{self.fullrelease}"

    @property
    def fullrelease(self):
        """Returns the release as a string, including dist and build if
        defined."""
        result = self.release
        if self.dist is not None:
            result += f".{self.dist}"
        if self.build >= 0:
            result += f"+build{self.build}"
        return result


class RegistryArtifact(ExportableType):

    EXFIELDS = {
        ExportableField('name'),
        ExportableField('architecture'),
        ExportableField('version'),
    }

    def __init__(self, name, architecture, version):
        self.name = name
        self.architecture = architecture
        self.version = version

    def __eq__(self, other):
        return (
            self.name == other.name
            and self.architecture == other.architecture
            and self.version == other.version
        )


class ChangelogEntry(ExportableType):

    EXFIELDS = {
        ExportableField('version'),
        ExportableField('author'),
        ExportableField('date', int),
        ExportableField('changes', list[str]),
    }

    def __init__(self, version, author, date, changes):
        self.version = version
        self.author = author
        self.date = date
        self.changes = changes
