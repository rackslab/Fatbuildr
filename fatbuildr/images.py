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

from .containers import ContainerRunner
from .pipelines import PipelinesDefs
from .templates import Templeter
from .log import logr

logger = logr(__name__)


class Image(object):

    def __init__(self, conf, instance, fmt):
        self.conf = conf
        self.format = fmt
        self.path = os.path.join(conf.images.storage, instance, self.format + '.img')
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

        logger.info("Creating image for %s format" % (self.format))
        cmd = Templeter.srender(self.conf.images.create_cmd,
                                definition=self.def_path,
                                path=self.path).split(' ')
        if self.conf.run.force:
            cmd.insert(1, '--force')

        logger.debug("Running command: %s", ' '.join(cmd))
        proc = subprocess.run(cmd)
        if proc.returncode:
            raise RuntimeError("Command failed with exit code %d: %s" \
                               % (proc.returncode, ' '.join(cmd)))

    def update(self):
        logger.info("Updating image for %s format" % (self.format))
        cmds = [ _cmd.strip() for _cmd in
                 getattr(self.conf, self.format).img_update_cmds.split('&&') ]
        ctn = ContainerRunner(self.conf.containers)
        for cmd in cmds:
            ctn.run_init(self, cmd)


class BuildEnv(object):

    def __init__(self, conf, image, name):
        self.conf = conf
        self.image = image
        self.name = name

    def create(self):
        logger.info("Create build environment %s in %s image" % (self.name, self.image.format))
        cmd = Templeter.srender(getattr(self.conf, self.image.format).init_cmd,
                                environment=self.name)
        ContainerRunner(self.conf.containers).run_init(self.image, cmd)

    def update(self):
        logger.info("Updating build environment %s in %s image" % (self.name, self.image.format))
        cmds = [ Templeter.srender(_cmd.strip(), environment=self.name)
                 for _cmd in
                 getattr(self.conf, self.image.format) \
                   .env_update_cmds.split('&&') ]
        ctn = ContainerRunner(self.conf.containers)
        for cmd in cmds:
            ctn.run_init(self.image, cmd)


class ImagesManager(object):

    def __init__(self, conf, instance):
        self.conf = conf
        self.instance = instance

    @property
    def selected_formats(self):
        if self.conf.run.format == 'all':
            return self.conf.images.formats
        return [self.conf.run.format]

    def create(self):
        if not os.path.exists(self.conf.images.storage):
            logger.debug("Creating missing images directory %s" % (self.conf.images.storage))
            os.mkdir(self.conf.images.storage)

        for _format in self.selected_formats:

            img = Image(self.conf, self.instance, _format)

            if img.exists and not self.conf.run.force:
                logger.error("Image %s already exists, use --force to ignore" % (img.def_path))
                continue

            if not img.def_exists:
                logger.error("Unable to find image definition file %s" % (img.def_path))
                continue

            try:
                img.create()
            except RuntimeError as err:
                logger.error("Error while creating the image %s: %s" % (img.path, err))

    def update(self):

        for _format in self.selected_formats:
            img = Image(self.conf, self.instance, _format)
            if not img.exists:
                logger.warning("Image %s does not exist, create it first" % (img.path))
                continue
            img.update()

    def create_envs(self):

        if not os.path.exists(self.conf.run.basedir):
            logger.error("Unable to find base directory %s" % (self.conf.run.basedir))
            sys.exit(1)

        logger.info("Creating build environments")
        # Load build environments declared in the basedir
        pipelines = PipelinesDefs(self.conf.run.basedir)

        for _format in self.selected_formats:
            img = Image(self.conf, self.instance, _format)
            distributions = pipelines.format_dists(_format)
            if not distributions:
                logger.info("No distribution defined for %s image"
                            % (_format))
            for _dist in distributions:
                env = BuildEnv(self.conf, img, pipelines.dist_env(_dist))
                env.create()

    def update_envs(self):

        logger.info("Updating build environments")
        # Load build environments declared in the basedir
        pipelines = PipelinesDefs(self.conf.run.basedir)

        for _format in self.selected_formats:
            img = Image(self.conf, self.instance, _format)
            for _dist in pipelines.format_dists(_format):
                env = BuildEnv(self.conf, img, pipelines.dist_env(_dist))
                env.update()
