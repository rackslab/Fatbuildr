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

from .exec import runcmd
from .utils import current_user
from .log import logr

logger = logr(__name__)


class ContainerRunner(object):
    def __init__(self, conf):
        self.conf = conf

    def __call__(
        self,
        image,
        cmd,
        init=False,
        opts=None,
        user=current_user()[1],  # run in container w/ the same user by default
        binds=[],
        chdir=None,
        envs=[],
        io=None,
        readonly=False,
    ):
        """Generic fully featured method to run command in container using
        systemd-nspawn."""
        _cmd = [
            self.conf.containers.exec,
            '--directory',
            image.path,
        ]

        if readonly:
            # Use --volatile=state option that mounts the image read-only with
            # a tmpfs for /var (data are lost after container shutdown). This
            # prevents the command from altering the image.
            #
            # Unfortunately, systemd-nspawn --read-only does not work with
            # --bind mounts, it fails with the following error:
            #
            # Failed to create mount point [/mnt/point]: Read-only file system
            _cmd.append('--volatile=state')

        # Bind-mount image format and common libdirs if they exist
        for path in [image.format_libdir, image.common_libdir]:
            if path.exists():
                _cmd.extend(['--bind', path])

        # add init_opts if init is True
        if init:
            _cmd.extend(self.conf.containers.init_opts)
        # add opts in args
        if opts is not None:
            _cmd.extend(opts)
        # add opts from conf
        if self.conf.containers.opts is not None:
            _cmd.extend(self.conf.containers.opts)
        if user != 'root':
            _cmd.extend(['--user', user])
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

        # Environment is set with NOTIFY_SOCKET=/dev/null to prevent
        # systemd-nspawn from notifying systemd its readiness. When
        # systemd-nspawn is run by fatbuildrd service, systemd PID 1 does not
        # expect notifications from systemd-nspawn, as it is not the main PID
        # of the service. These notifications cause spurious warning messages
        # from systemd in service logs, such as:
        #
        #   "Got notification message from PID xxx, but reception only
        #    permitted for main PID"
        #
        # One solution is to tune environment to make systemd-nspawn sends its
        # notifications elsewhere. Note that the purpose of systemd-nspawn
        # --notify-ready=no is totally different.
        runcmd(_cmd, env={'NOTIFY_SOCKET': '/dev/null'}, io=io)
