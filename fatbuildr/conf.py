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
import logging

logger = logging.getLogger(__name__)

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
        self.img = config.get(section, 'img')
        self.queue = config.get(section, 'queue')
        self.state = config.get(section, 'state')
        self.repos = config.get(section, 'repos')
        self.cache = config.get(section, 'cache')
        self.tmp = config.get(section, 'tmp')

    def dump(self):
        logger.debug("[dirs]")
        logger.debug("  img: %s" % (self.img))
        logger.debug("  queue: %s" % (self.queue))
        logger.debug("  state: %s" % (self.state))
        logger.debug("  repos: %s" % (self.repos))
        logger.debug("  cache: %s" % (self.cache))
        logger.debug("  tmp: %s" % (self.tmp))

class RuntimeConf(object):
    """Runtime configuration class for all Fatbuildr applications."""

    def __init__(self):
        self.dirs = RuntimeConfDirs()
        self.instance = None

    def load(self):
        """Load configuration files and set runtime parameters accordingly."""
        config = configparser.ConfigParser()
        # read vendor configuration file and override with site specific
        # configuration file
        vendor_conf_path = '/usr/lib/fatbuildr/fatbuildr.ini'
        site_conf_path = '/etc/fatbuildr/fatbuildr.ini'
        logger.debug("Loading vendor configuration file %s" % (vendor_conf_path))
        config.read_file(open(vendor_conf_path))
        logger.debug("Loading site specific configuration file %s" % (site_conf_path))
        config.read_file(open(site_conf_path))

        self.dirs.load(config)
        self.instance = config.get('main', 'default_instance')

    def dump(self):
        """Dump all runtime configuration parameters when in debug mode."""

        if not logger.isEnabledFor(logging.DEBUG):
            return
        logger.debug("[main]")
        logger.debug("  instance: %s" % (self.instance))
        self.dirs.dump()
