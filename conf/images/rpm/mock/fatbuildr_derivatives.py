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

from pathlib import Path

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

        repo = Path(self.opts['repo'])
        keyring = Path(self.opts['keyring'])

        if self.buildroot.is_bootstrap:
            # During the boostrap phase, add bind-mount of the repo directory in
            # the final chroot, if it exists.
            if repo.exists():
                mountpoint = self.buildroot.make_chroot_path(str(repo))
                self.buildroot.mounts.add(
                    BindMountPoint(srcpath=repo, bindpath=mountpoint)
                )
                getLog().info(
                    "Add bind-mount of repository directory %s in chroot", repo
                )
            else:
                getLog().info(
                    "Skipping bind-mount of %s in chroot because unexisting",
                    repo,
                )
            # Also bind-mount the keyring directory in the final chroot, if the
            # keyring is available, so dnf/yum can access it.
            if keyring.exists():
                mountpoint = self.buildroot.make_chroot_path(
                    str(keyring.parent)
                )
                self.buildroot.mounts.add(
                    BindMountPoint(srcpath=keyring.parent, bindpath=mountpoint)
                )
                getLog().info(
                    "Add bind-mount of keyring directory %s in chroot",
                    keyring.parent,
                )
        else:
            # In the final chroot, add all the build derivatives repositories in
            # dnf configuration file content, with descending priorities.
            priority = 50  # first derivative priority
            for derivative in reversed(self.opts['derivatives'].split(',')):
                repos_dir = repo.joinpath(self.opts['distribution'], derivative)
                if not repos_dir.joinpath(
                    'source', 'repodata', 'repomd.xml'
                ).exists():
                    getLog().info(
                        "skipping derivative %s as %s repository metadata does "
                        "not exist",
                        derivative,
                        repos_dir,
                    )
                    continue
                output = '\n'.join(
                    [
                        f"[fatbuildr-{self.opts['distribution']}-{derivative}]",
                        f"name=Fatbuildr-{self.opts['distribution']}-{derivative}",
                        f"baseurl=file://{repos_dir}/$basearch",
                        'enabled=1',
                        f"priority={priority}",
                        f"gpgkey=file://{keyring}",
                        'gpgcheck=1',
                        'skip_if_unavailable=False',
                        '',
                    ]
                )
                getLog().info("generated additional dnf.conf:\n%s", output)
                self.config['dnf.conf'] += output
                priority -= 1
