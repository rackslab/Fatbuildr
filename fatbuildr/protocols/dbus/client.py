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

import subprocess

from . import REGISTER, DbusSubmittedBuild, DbusRunningBuild, DbusArchivedBuild, ErrorNoRunningBuild


class DbusClient(object):
    def __init__(self):
        self.proxy = REGISTER.get_proxy()

    def submit(self, place):
        return self.proxy.Submit(place)

    def queue(self):
        return DbusSubmittedBuild.from_structure_list(self.proxy.Queue)

    def running(self):
        try:
            return DbusRunningBuild.from_structure(self.proxy.Running)
        except ErrorNoRunningBuild:
            return None

    def archives(self):
        return DbusArchivedBuild.from_structure_list(self.proxy.Archives)

    def get(self, build_id):
        for _build in self.queue():
            if _build.id == build_id:
                return _build
        _running = self.running()
        if _running and _running.id == build_id:
            return _running
        for _build in self.archives():
            if _build.id == build_id:
                return _build
        raise RuntimeError("Unable to find build %s on server" % (build_id))

    def watch(self, build):
        """Dbus clients run on the same host as the server, they access the
           builds log files directly."""
        assert hasattr(build, 'logfile')
        if build.state == 'running':
            # Follow the log file. It has been choosen to exec `tail -f`
            # because python lacks well maintained and common inotify library.
            # This tail command is in coreutils and it is installed basically
            # everywhere.
            cmd = ['tail', '--follow', build.logfile]
            subprocess.run(cmd)
        else:
            # dump full build log
            with open(build.logfile, 'r') as fh:
                 while chunk := fh.read(8192):
                    print(chunk, end='')
