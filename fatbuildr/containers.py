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

from .utils import runcmd
from .log import logr

logger = logr(__name__)


class ContainerRunner(object):
    def __init__(self, conf):
        self.conf = conf

    def run(
        self,
        image,
        cmd,
        init=False,
        opts=None,
        binds=[],
        chdir=None,
        envs=[],
        log=None,
    ):
        """Generic fully featured method to run command in container using
        systemd-nspawn."""
        _cmd = [
            'systemd-nspawn',
            '--directory',
            image.path,
        ]

        # Bind-mount image format subdir if it exists
        img_dir_path = f"/usr/lib/fatbuildr/images/{image.format}"
        if os.path.exists(img_dir_path):
            _cmd.extend(['--bind', img_dir_path])

        # add init_opts if init is True
        if init:
            _cmd.extend(self.conf.init_opts)
        # add opts in args
        if opts is not None:
            _cmd.extend(opts)
        # add opts from conf
        if self.conf.opts is not None:
            _cmd.extend(self.conf.opts)
        for _bind in binds:
            _cmd.extend(['--bind', _bind])
        if chdir is not None:
            _cmd.extend(['--chdir', chdir])
        for _env in envs:
            _cmd.extend(['--setenv', _env])
        if isinstance(cmd, str):
            _cmd.extend(cmd.split(' '))
        else:
            _cmd.extend(cmd)
        runcmd(_cmd, log=log)
