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

from pathlib import Path

from mockbuild.trace_decorator import getLog, traceLog

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    FatbuildrList(plugins, conf, buildroot)


class FatbuildrList:
    """Mock plugin to list content of built RPM packages after a build success
    to have a quick glance of the build result."""

    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.state = buildroot.state
        self.opts = conf
        plugins.add_hook("postbuild", self._PostBuildHook)

    @traceLog()
    def _PostBuildHook(self):
        getLog().info(
            "starting FatbuildrList plugin to list content of RPM packages"
        )
        if self.state.result != "success":
            getLog().info("skipping content listing after failing build")
            return
        rpm_dir = Path(
            self.buildroot.make_chroot_path(self.buildroot.builddir, 'RPMS')
        )
        for rpm_path in rpm_dir.glob('*.rpm'):
            print("\n-- Content of RPM packages", rpm_path.name)
            self.buildroot.doChroot(
                [
                    'rpm',
                    '--query',
                    '--queryformat',
                    (
                        "[%{FILEMODES:perms} "
                        "%8{FILEUSERNAME}/%-8{FILEGROUPNAME} "
                        "%7{FILESIZES:humansi} "
                        "%-36{FILENAMES}\n]"
                    ),
                    '--package',
                    rpm_path.relative_to(self.buildroot.make_chroot_path()),
                ],
                printOutput=True,
            )
