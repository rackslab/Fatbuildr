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
# our imports

import os

from mockbuild.mounts import BindMountPoint
from mockbuild.trace_decorator import getLog, traceLog
import mockbuild.util

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    FatbuildrDerivatives(plugins, conf, buildroot)


class FatbuildrDerivatives:
    """Mock plugin to add all required internal repos, including derivatives,
    in the build environment."""

    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.procenv_opts = conf
        self.config = buildroot.config
        self.opts = conf
        plugins.add_hook("preinit", self._PreInitHook)

    @traceLog()
    def _PreInitHook(self):
        getLog().info("enabled FatbuildrDerivatives plugin")

        if self.buildroot.is_bootstrap:
            # During the boostrap phase, add bind-mount of the repo directory in
            # the final chroot.
            mountpoint = self.buildroot.make_chroot_path(self.opts['repo'])
            self.buildroot.mounts.add(
                BindMountPoint(srcpath=self.opts['repo'], bindpath=mountpoint)
            )
            getLog().info("Add bind-mount of %s in chroot", self.opts['repo'])
        else:
            # In the final chroot, add all the build derivatives repositories in
            # dnf configuration file content, with descending priorities.
            priority = 50  # first derivative priority
            for derivative in reversed(self.opts['derivatives'].split(',')):
                repos_dir = (
                    f"{self.opts['repo']}/{self.opts['distribution']}/"
                    f"{derivative}"
                )
                if not os.path.exists(repos_dir):
                    getLog().info(
                        "skipping derivative %s as %s directory does not exist",
                        derivative,
                        repos_dir,
                    )
                    continue
                output = '\n'.join(
                    [
                        f"[fatbuildr-{self.opts['distribution']}-{derivative}]",
                        f"name=Fatbuildr-{self.opts['distribution']}-{derivative}",
                        f"baseurl=file://{repos_dir}",
                        'enabled=1',
                        f"priority={priority}",
                        f"gpgkey=file://{self.opts['keyring']}",
                        'gpgcheck=1',
                        'skip_if_unavailable=False',
                        '',
                    ]
                )
                getLog().info("generated additional dnf.conf:\n%s", output)
                self.config['dnf.conf'] += output
                priority -= 1
