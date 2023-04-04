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

from .log import logr

logger = logr(__name__)


class CacheArtifact(object):
    def __init__(self, dir, build):
        self.dir = dir.joinpath(build.artifact)
        self.build = build

    def archive(self, source_id):
        return self.dir.joinpath(
            self.build.defs.source(source_id).filename(self.build.derivative)
        )

    def has_archive(self, source_id):
        return self.archive(source_id).exists()

    def ensure(self):
        if not self.dir.exists():
            logger.info(
                "Creating instance artifact cache directory %s", self.dir
            )
            self.dir.mkdir()
            self.dir.chmod(0o755)  # be umask agnostic


class CacheManager:
    def __init__(self, conf, instance):
        self.dir = conf.dirs.cache.joinpath(instance.id)
        if not self.dir.exists():
            logger.info("Creating instance cache directory %s", self.dir)
            self.dir.mkdir()
            self.dir.chmod(0o755)  # be umask agnostic

    def artifact(self, build):
        return CacheArtifact(self.dir, build)
