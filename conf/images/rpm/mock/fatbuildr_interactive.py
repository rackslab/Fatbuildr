#!/usr/bin/env python3
#
# Copyright (C) 2023 Rackslab
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

import subprocess

from mockbuild.trace_decorator import getLog, traceLog
from mockbuild.util import ChildPreExec

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    FatbuildrInteractive(plugins, conf, buildroot)


class FatbuildrInteractive:
    """Mock plugin to run interactive shell in the build environment after a
    build failure and help users to diagnose the cause."""

    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.state = buildroot.state
        self.opts = conf
        plugins.add_hook("postbuild", self._PostBuildHook)

    @traceLog()
    def _PostBuildHook(self):
        getLog().info("enabled FatbuildrInteractive plugin")
        if self.state.result != "fail":
            getLog().info("skipping interactive shell after successful build")
            return
        if self.opts['enabled'] != 'yes':
            getLog().info(
                "interactive shell after failure is disabled, skipping"
            )
            return
        self.buildroot.install('vim', 'less')
        # Unfortunately, self.buildroot.doChroot() cannot be used to launch the
        # interactive shell as it binds process stdin to /dev/null and the shell
        # terminates immediately. The solution is to immitate do
        # util.do_with_status() by calling subprocess with ChildPreExec as
        # preexec_fn to prepare execution environment in build chroot.
        preexec = ChildPreExec(
            None,
            self.buildroot.make_chroot_path(),
            None,
            None,
            None,
            unshare_ipc=True,
            unshare_net=True,
        )
        subprocess.run(
            ['bash'],
            preexec_fn=preexec,
        )
        getLog().info("leaving interactive shell")
