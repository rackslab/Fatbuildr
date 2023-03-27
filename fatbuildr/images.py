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

import tarfile
from io import BytesIO

from .templates import Templeter
from .utils import current_user_group, current_user
from .exec import runcmd
from .specifics import ArchMap
from .log import logr

logger = logr(__name__)


class Image(object):
    def __init__(self, conf, instance, fmt):
        self.conf = conf
        self.format = fmt
        self.path = conf.images.storage.joinpath(
            instance, self.format
        ).with_suffix('.img')
        self.format_libdir = conf.images.defs.joinpath(self.format)
        self.common_libdir = conf.images.defs.joinpath('common')
        self.def_path = conf.images.defs.joinpath(self.format).with_suffix(
            '.mkosi'
        )
        self.skel_path = conf.images.storage.joinpath('skeleton.tar.xz')

    @property
    def exists(self):
        return self.path.exists()

    @property
    def def_exists(self):
        return self.def_path.exists()

    @property
    def builder(self):
        return getattr(self.conf, self.format).builder

    @property
    def prescript_deps(self):
        return getattr(self.conf, self.format).prescript_deps

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

        # Generate skeleton archive with sysusers.d configuration file to
        # create user/group running fatbuildrd, with the same UID/GID, inside
        # the container.
        #
        # It is deployed using mkosi skeleton to make sure it is deployed
        # before packages are installed in the container image, ie. before
        # the first time systemd-sysusers is run, and prevent other sysusers
        # from being created with the same UID/GID.
        logger.info("Generating skeleton archive %s", self.skel_path)

        # Remove existing skeleton archive if it has already been generated
        # previously.
        if self.skel_path.exists():
            logger.debug(
                "Removing existing skeleton archive %s", self.skel_path
            )
            self.skel_path.unlink()

        with tarfile.open(self.skel_path, 'x:xz') as tar:
            (uid, user, gid, group) = current_user_group()
            content = (
                f"g {group} {gid}\n"
                f"u {user} {uid}:{gid} \"Fatbuildr user\"\n"
            ).encode()
            tarinfo = tarfile.TarInfo(name="usr/lib/sysusers.d/fatbuildr.conf")
            tarinfo.size = len(content)
            tarinfo.mode = 0o644
            tar.addfile(tarinfo, BytesIO(content))

        logger.info("Creating image for %s format", self.format)
        cmd = (
            Templeter()
            .srender(
                self.conf.images.create_cmd,
                format=self.format,
                definition=str(self.def_path),
                dirpath=str(self.path.parent),
                path=str(self.path),
                skeleton=str(self.skel_path),
                user=user,
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
            # Package manager must be run as root
            task.cruncmd(self, cmd, init=True, asroot=True)

    def shell(self, task, term):
        logger.info(
            "Launching interactive shell in image for %s format", self.format
        )
        if not self.exists:
            raise RuntimeError(
                f"Image {self.path} does not exist, create it first"
            )
        task.cruncmd(self, None, envs=[f"TERM={term}"], init=True, asroot=True)


class BuildEnv(object):
    def __init__(self, conf, image, environment, architecture, pipelines):
        self.conf = conf
        self.image = image
        self.environment = environment
        self.architecture = architecture
        self.pipelines = pipelines

    def __str__(self):
        return f"{self.environment}-{self.architecture}"

    @property
    def path(self):
        env_path = getattr(self.conf, self.image.format).env_path
        if env_path:
            return Templeter().srender(env_path, name=self.name)

    @property
    def name(self):
        return f"{self.environment}-{self.native_architecture}"

    @property
    def native_architecture(self):
        return ArchMap(self.image.format).native(self.architecture)

    def create(self, task):
        logger.info(
            "Creating build environment %s for architecture %s in %s image",
            self.environment,
            self.architecture,
            self.image.format,
        )

        # check init_cmd is defined for this format
        if getattr(self.conf, self.image.format).init_cmd is None:
            raise RuntimeError(
                f"Unable to create build environment {self.name} for "
                f"architecture {self.architecture} in {self.image.format} "
                "image because init_cmd is not defined for this format"
            )

        # Get the mirror defined in instance pipelines definition
        mirror = self.pipelines.env_mirror(self.environment)
        if mirror is None:
            # If the mirror is not defined in pipelines definition, get the
            # environment default mirror in system configuration. If it is also
            # not defined in system configuration (it is not available for all
            # formats), fallback to None.
            try:
                mirror = getattr(
                    self.conf, self.image.format
                ).env_default_mirror
            except AttributeError:
                mirror = None

        # Get the components defined in instance pipelines definition
        components = self.pipelines.env_components(self.environment)
        if components is None:
            # If the components is not defined in pipelines definition, get the
            # environment default components in system configuration. If it is
            # also not defined in system configuration (it is not available for
            # all formats), fallback to None.
            try:
                components = getattr(
                    self.conf, self.image.format
                ).env_default_components
            except AttributeError:
                components = None
        # Define if the environment creation command must be run as root in
        # container.
        asroot = getattr(self.conf, self.image.format).env_as_root

        cmd = Templeter().srender(
            getattr(self.conf, self.image.format).init_cmd,
            environment=self.environment,
            mirror=mirror,
            components=components,
            architecture=self.native_architecture,
            name=self.name,
            path=self.path,
        )
        task.cruncmd(self.image, cmd, init=True, asroot=asroot)

    def update(self, task):
        logger.info(
            "Updating build environment %s for architecture %s in %s image",
            self.name,
            self.architecture,
            self.image.format,
        )
        # Define if the environment update command must be run as root in
        # container.
        asroot = getattr(self.conf, self.image.format).env_as_root
        cmds = [
            Templeter().srender(
                _cmd.strip(),
                environment=self.environment,
                architecture=self.native_architecture,
                name=self.name,
                path=self.path,
            )
            for _cmd in getattr(
                self.conf, self.image.format
            ).env_update_cmds.split('&&')
        ]
        for cmd in cmds:
            task.cruncmd(self.image, cmd, init=True, asroot=asroot)

    def shell(self, task, term):
        logger.info(
            "Running a shell in build environment %s for architecture %s in %s "
            "image",
            self.name,
            self.architecture,
            self.image.format,
        )
        cmd = Templeter().srender(
            getattr(self.conf, self.image.format).shell_cmd,
            environment=self.environment,
            architecture=self.native_architecture,
            name=self.name,
            path=self.path,
        )
        task.cruncmd(
            self.image, cmd, envs=[f"TERM={term}"], init=True, asroot=True
        )


class ImagesManager(object):
    def __init__(self, conf, instance):
        self.conf = conf
        self.instance = instance

    def image(self, format):
        return Image(self.conf, self.instance.id, format)

    def build_env(self, format, name, architecture):
        return BuildEnv(
            self.conf,
            self.image(format),
            name,
            architecture,
            self.instance.pipelines,
        )

    def prepare(self):
        """Creates images storage directory if it is missing."""
        path = self.conf.images.storage.joinpath(self.instance.name)
        if not path.exists():
            logger.info("Creating instance image directory %s", path)
            path.mkdir()
            path.chmod(0o755)  # be umask agnostic
