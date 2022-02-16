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

from .log import logr

logger = logr(__name__)


class ArchivesManager:
    def __init__(self, conf):
        self.conf = conf

    def save_build(self, build):
        archives_dir = os.path.join(self.conf.dirs.archives, build.instance.id)
        if not os.path.exists(archives_dir):
            logger.debug(
                "Creating instance archives directory %s", archives_dir
            )
            os.mkdir(archives_dir)
            os.chmod(archives_dir, 0o755)  # be umask agnostic

        dest = os.path.join(archives_dir, build.id)
        logger.info(
            "Moving build directory %s to archives directory %s",
            build.place,
            dest,
        )
        shutil.move(build.place, dest)
