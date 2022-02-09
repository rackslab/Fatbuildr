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
import subprocess

from .log import logr

logger = logr(__name__)


class ContainerRunner(object):
    def __init__(self, conf):
        self.conf = conf

    def run_init(self, image, envcmd):
        self.run(image, envcmd, opts=self.conf.init_opts)

    def run(
        self,
        image,
        runcmd,
        opts=None,
        binds=[],
        chdir=None,
        envs=[],
        logfile=None,
    ):
        """Generic fully featured method to run command in container using
        systemd-nspawn."""
        cmd = [
            'systemd-nspawn',
            '--directory',
            image.path,
        ]

        # Bind-mount image format subdir if it exists
        img_dir_path = f"/usr/lib/fatbuildr/images/{image.format}"
        if os.path.exists(img_dir_path):
            cmd.extend(['--bind', img_dir_path])

        # add opts in args
        if opts is not None:
            cmd.extend(opts)
        # add opts from conf
        if self.conf.opts is not None:
            cmd.extend(self.conf.opts)
        for _bind in binds:
            cmd.extend(['--bind', _bind])
        if chdir is not None:
            cmd.extend(['--chdir', chdir])
        for _env in envs:
            cmd.extend(['--setenv', _env])
        if isinstance(runcmd, str):
            cmd.extend(runcmd.split(' '))
        else:
            cmd.extend(runcmd)
        logger.debug("Running command: %s", ' '.join(cmd))
        fh = None
        if logfile is not None:
            fh = open(logfile, 'a')
        proc = subprocess.run(cmd, stdout=fh, stderr=fh)
        if fh is not None:
            fh.close()
        if proc.returncode:
            raise RuntimeError(
                f"Command failed with exit code {proc.returncode}: "
                f"{' '.join(cmd)}"
            )
