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
        self.conf = conf
        self.format = fmt
        self.path = os.path.join(conf.images.storage, conf.app.instance, self.format + '.img')
        self.def_path = os.path.join(conf.images.defs, self.format + '.mkosi')

    @property
    def exists(self):
        return os.path.exists(self.path)

    @property
    def def_exists(self):
        return os.path.exists(self.def_path)

    def create(self):
        """Create the image."""

        # ensure instance images directory is present
        _dirname = os.path.dirname(self.path)
        if not os.path.exists(_dirname):
            logger.info("Creating instance image directory %s" % (_dirname))
            os.mkdir(_dirname)
            os.chmod(_dirname, 0o755)  # be umask agnostic

        logger.info("Creating image for format %s" % (self.format))
        cmd = Templeter.args(self.conf.images.create_cmd,
                             definition=self.def_path,
                             path=self.path).split(' ')
        if self.conf.app.force:
            cmd.insert(1, '--force')
        subprocess.run(cmd)

    def update(self):
        logger.info("Updating image for format %s" % (self.format))
        cmds = [ _cmd.strip() for _cmd in
                 getattr(self.conf, self.format).img_update_cmds.split('&&') ]
        ctn = ContainerRunner(self.conf.containers)
        for cmd in cmds:
            ctn.run(self, cmd)


class BuildEnv(object):

    def __init__(self, conf, image, name):
        self.conf = conf
        self.image = image
        self.name = name

    def create(self):
        logger.info("Create build environment %s in %s image" % (self.name, self.image.format))
        cmd = Templeter.args(getattr(self.conf, self.image.format).init_cmd,
                             environment=self.name)
        ContainerRunner(self.conf.containers).run_init(self.image, cmd)

    def update(self):
        logger.info("Updating build environment %s in %s image" % (self.name, self.image.format))
        cmds = [ Templeter.args(_cmd.strip(), environment=self.name) for _cmd in
                 getattr(self.conf, self.image.format).env_update_cmds.split('&&') ]
        ctn = ContainerRunner(self.conf.containers)
        for cmd in cmds:
            ctn.run(self.image, cmd)


class ImagesManager(object):

    def __init__(self, conf):
        self.conf = conf

    def create(self):
        if not os.path.exists(self.conf.images.storage):
            logger.debug("Creating missing images directory %s" % (self.conf.images.storage))
            os.mkdir(self.conf.images.storage)

        for _format in self.conf.images.formats:

            img = Image(self.conf, _format)

            if img.exists and not self.conf.app.force:
                logger.error("Image %s already exists, use --force to ignore" % (img.def_path))
                sys.exit(1)

            if not img.def_exists:
                logger.error("Unable to find image definition file %s" % (img.def_path))
                sys.exit(1)

            img.create()

    def update(self):

        for _format in self.conf.images.formats:
            img = Image(self.conf, _format)
            if not img.exists:
                logger.warning("Image %s does not exist, create it first" % (img.path))
                continue
            img.update()

    def create_envs(self):

        if not os.path.exists(self.conf.app.basedir):
            logger.error("Unable to find base directory %s" % (self.conf.app.basedir))
            sys.exit(1)

        logging.info("Creating build environments")
        # Load build environments declared in the basedir
        pipelines = PipelinesDefs(self.conf.app.basedir)

        for _format in self.conf.images.formats:
            img = Image(self.conf, _format)
            for _dist in pipelines.format_dists(_format):
                env = BuildEnv(self.conf, img, pipelines.dist_env(_dist))
                env.create()

    def update_envs(self):

        logging.info("Updating build environments")
        # Load build environments declared in the basedir
        pipelines = PipelinesDefs(self.conf.app.basedir)

        for _format in self.conf.images.formats:
            img = Image(self.conf, _format)
            for _dist in pipelines.format_dists(_format):
                env = BuildEnv(self.conf, img, pipelines.dist_env(_dist))

                env.update()
