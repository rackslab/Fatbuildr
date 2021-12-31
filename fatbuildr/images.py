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
import sys
import subprocess
import logging

logger = logging.getLogger(__name__)

class ImagesManager(object):

    def __init__(self, conf):
        self.conf = conf

    def create(self):
        if not os.path.exists(self.conf.images.storage):
            logger.debug("Creating missing images directory %s" % (self.conf.images.storage))
            os.mkdir(self.conf.images.storage)

        for _format in self.conf.images.formats:
            def_path = os.path.join(self.conf.images.defs, _format + '.mkosi')
            if not os.path.exists(def_path):
                logger.error("Unable to find image definition file %s" % (def_path))
                sys.exit(1)

            logging.info("Creating image for format %s" % (_format))
            cmd = ['mkosi', '--default', def_path ]
            if self.conf.ctl.force:
                cmd.insert(1, '--force')
            subprocess.run(cmd)
