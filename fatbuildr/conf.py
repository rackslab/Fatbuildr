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

import configparser


class RuntimeConfDirs(object):
    """Runtime configuration class to hold directories paths."""

    def __init__(self):

        self.img = None
        self.queue = None
        self.state = None
        self.repos = None
        self.cache = None
        self.tmp = None

    def load(self, config):
        section = 'dirs'
        self.img = config.get(section, 'images')
        self.queue = config.get(section, 'queue')
        self.state = config.get(section, 'state')
        self.repos = config.get(section, 'repos')
        self.cache = config.get(section, 'cache')
        self.tmp = config.get(section, 'tmp')


class RuntimeConf(object):
    """Runtime configuration class for all Fatbuildr applications."""

    def __init__(self):
        self.dirs = RuntimeConfDirs()

    def load(self):
        config = configparser.ConfigParser()
        # read vendor configuration file and override with site specific
        # configuration file
        config.read_file(open('/usr/lib/fatbuildr/fatbuildr.ini'))
        config.read_file(open('/etc/fatbuildr/fatbuildr.ini'))

        self.dirs.load(config)
