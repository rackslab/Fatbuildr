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

from .templates import Templeter
from .utils import runcmd
from .log import logr

logger = logr(__name__)


class Image(object):
    def __init__(self, conf, instance, fmt):
        self.conf = conf
        self.format = fmt
        self.path = conf.images.storage.joinpath(
            instance, self.format
        ).with_suffix('.img')
        self.def_path = conf.images.defs.joinpath(self.format).with_suffix(
            '.mkosi'
        )

    @property
    def exists(self):
        return self.path.exists()

    @property
    def def_exists(self):
        return self.def_path.exists()

    def create(self, task, force):
        """Create the image."""
        logger.info("Creating image for %s format", self.format)

        if self.exists and not force:
            raise RuntimeError(
                f"Image {self.def_path} already exists, use force to ignore"
            )

        if not self.def_exists:
            raise RuntimeError(
                f"Unable to find image definition file {self.def_path}"
            )

        # ensure instance images directory is present
        _dirname = self.path.parent
        if not _dirname.exists():
            logger.info("Creating instance image directory %s", _dirname)
            _dirname.mkdir()
            _dirname.chmod(0o755)  # be umask agnostic

        logger.info("Creating image for %s format", self.format)
        cmd = (
            Templeter()
            .srender(
                self.conf.images.create_cmd,
                format=self.format,
                definition=str(self.def_path),
                dirpath=str(self.path.parent),
                path=str(self.path),
            )
            .split(' ')
        )
        if force:
            cmd.insert(1, '--force')

        task.runcmd(cmd)

    def update(self, task):
        logger.info("Updating image for %s format", self.format)
        if not self.exists:
            raise RuntimeError(
                f"Image {self.path} does not exist, create it first"
            )
        cmds = [
            _cmd.strip()
            for _cmd in getattr(self.conf, self.format).img_update_cmds.split(
                '&&'
            )
        ]
        for cmd in cmds:
            task.cruncmd(self, cmd, init=True)


class BuildEnv(object):
    def __init__(self, conf, image, name):
        self.conf = conf
        self.image = image
        self.name = name

    def create(self, task):
        logger.info(
            "Creating build environment %s in %s image",
            self.name,
            self.image.format,
        )

        # check init_cmd is defined for this format
        if getattr(self.conf, self.image.format).init_cmd is None:
            raise RuntimeError(
                f"Unable to create build environment {self.name} in "
                f"{self.image.format} image because init_cmd is not defined "
                "for this format"
            )

        cmd = Templeter().srender(
            getattr(self.conf, self.image.format).init_cmd,
            environment=self.name,
        )
        task.cruncmd(self.image, cmd, init=True)

    def update(self, task):
        logger.info(
            "Updating build environment %s in %s image",
            self.name,
            self.image.format,
        )
        cmds = [
            Templeter().srender(_cmd.strip(), environment=self.name)
            for _cmd in getattr(
                self.conf, self.image.format
            ).env_update_cmds.split('&&')
        ]
        for cmd in cmds:
            task.cruncmd(self.image, cmd, init=True)


class ImagesManager(object):
    def __init__(self, conf, instance):
        self.conf = conf
        self.instance = instance

    @property
    def defs_path(self):
        return self.conf.images.defs

    def image(self, format):
        return Image(self.conf, self.instance, format)

    def build_env(self, format, name):
        return BuildEnv(self.conf, self.image(format), name)

    def prepare(self):
        """Creates images storage directory if it is missing."""
        if not self.conf.images.storage.exists():
            logger.debug(
                "Creating missing images directory %s", self.conf.images.storage
            )
            self.conf.images.storage.mkdir()
