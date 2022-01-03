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

from .containers import ContainerRunner
from .pipelines import PipelinesDefs
from .templates import Templeter

logger = logging.getLogger(__name__)


class Image(object):

    def __init__(self, conf, fmt):
        self.format = fmt
        self.path = os.path.join(conf.images.storage, self.format + '.img')
        self.def_path = os.path.join(conf.images.defs, self.format + '.mkosi')


class ImagesManager(object):

    def __init__(self, conf):
        self.conf = conf

    def create(self):
        if not os.path.exists(self.conf.images.storage):
            logger.debug("Creating missing images directory %s" % (self.conf.images.storage))
            os.mkdir(self.conf.images.storage)

        for _format in self.conf.images.formats:

            img = Image(self.conf, _format)
            if not os.path.exists(img.def_path):
                logger.error("Unable to find image definition file %s" % (img.def_path))
                sys.exit(1)

            logging.info("Creating image for format %s" % (_format))
            cmd = ['mkosi', '--default', img.def_path ]
            if self.conf.ctl.force:
                cmd.insert(1, '--force')
            subprocess.run(cmd)

    def create_envs(self):

        if not os.path.exists(self.conf.ctl.basedir):
            logger.error("Unable to find base directory %s" % (self.conf.ctl.basedir))
            sys.exit(1)

        logging.info("Creating build environments")
        # Load build environments declared in the basedir
        pipelines = PipelinesDefs(self.conf.ctl.basedir)
        # Initialize container runner
        ctn = ContainerRunner(self.conf.containers)

        for _format in self.conf.images.formats:
            img = Image(self.conf, _format)
            for _dist in pipelines.format_dists(_format):
                cmd = Templeter.args(getattr(self.conf, _format).init_cmd,
                                     environment=pipelines.dist_env(_dist))
                ctn.run_init(img, cmd)
