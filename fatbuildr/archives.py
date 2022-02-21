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
import shutil

from .builds import BuildArchive
from .log import logr

logger = logr(__name__)


class ArchivesManager:
    def __init__(self, conf, instance):
        self.instance = instance
        self.path = os.path.join(conf.dirs.archives, instance.id)

    def save_task(self, task, form=None):
        if not os.path.exists(self.path):
            logger.debug("Creating instance archives directory %s", self.path)
            os.mkdir(self.path)
            os.chmod(self.path, 0o755)  # be umask agnostic

        dest = os.path.join(self.path, task.id)
        logger.info(
            "Moving task directory %s to archives directory %s",
            task.place,
            dest,
        )
        shutil.move(task.place, dest)

        # Save task form, if defined
        if form:
            form.save(dest)

    def dump(self):
        """Returns all BuildArchive found in archives directory."""
        _archives = []

        for build_id in os.listdir(self.path):
            try:
                _archives.append(
                    BuildArchive(
                        build_id,
                        os.path.join(self.path, build_id),
                        self.instance,
                    )
                )
            except FileNotFoundError as err:
                logger.error(
                    "Unable to load malformed build archive %s: %s",
                    build_id,
                    err,
                )
        return _archives
