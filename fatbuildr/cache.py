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


class CacheArtefact(object):

    def __init__(self, conf, instance, artefact):
        self.instance_dir = os.path.join(conf.dirs.cache, instance)
        self.dir = os.path.join(self.instance_dir, artefact.name)
        self.artefact = artefact

    @property
    def tarball_path(self):
        return os.path.join(self.dir, os.path.basename(self.artefact.tarball))

    @property
    def has_tarball(self):
        return os.path.exists(self.tarball_path)

    def ensure(self):
        if not os.path.exists(self.instance_dir):
            logger.info("Creating instance cache directory %s" % (self.instance_dir))
            os.mkdir(self.instance_dir)
            os.chmod(self.instance_dir, 0o755)  # be umask agnostic

        if not os.path.exists(self.dir):
            logger.info("Creating artefact cache directory %s" % (self.dir))
            os.mkdir(self.dir)
            os.chmod(self.dir, 0o755)  # be umask agnostic
