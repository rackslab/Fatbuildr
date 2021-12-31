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


class RuntimeSubConfDirs(object):
    """Runtime sub-configuration class to hold directories paths."""

    def __init__(self):

        self.img = None
        self.queue = None
        self.state = None
        self.repos = None
        self.cache = None
        self.tmp = None

    def load(self, config):
        section = 'dirs'
        self.queue = config.get(section, 'queue')
        self.state = config.get(section, 'state')
        self.repos = config.get(section, 'repos')
        self.cache = config.get(section, 'cache')
        self.tmp = config.get(section, 'tmp')

    def dump(self):
        logger.debug("[dirs]")
        logger.debug("  queue: %s" % (self.queue))
        logger.debug("  state: %s" % (self.state))
        logger.debug("  repos: %s" % (self.repos))
        logger.debug("  cache: %s" % (self.cache))
        logger.debug("  tmp: %s" % (self.tmp))


class RuntimeSubConfImages(object):
    """Runtime sub-configuration class to hold images settings."""

    def __init__(self):

        self.storage = None
        self.defs = None
        self.formats = None

    def load(self, config):
        section = 'images'
        self.storage = config.get(section, 'storage')
        self.defs = config.get(section, 'defs')
        self.formats = config.get(section, 'formats').split(',')

    def dump(self):
        logger.debug("[images]")
        logger.debug("  storage: %s" % (self.storage))
        logger.debug("  defs: %s" % (self.defs))
        logger.debug("  formats: %s" % (self.formats))


class RuntimeSubConfCtl(object):
    """Runtime sub-configuration class to ctl parameters."""

    def __init__(self):
        self.instance = None
        self.action = None
        # parameters for image action
        self.operation = None
        self.force = None
        # parameters for package action
        self.package = None
        self.basedir = None

    def load(self, config):
       self.instance = config.get('ctl', 'default_instance')

    def dump(self):
        logger.debug("[ctl]")
        logger.debug("  instance: %s" % (self.instance))
        logger.debug("  action: %s" % (self.action))
        logger.debug("  operation: %s" % (self.operation))
        logger.debug("  force: %s" % (self.force))
        logger.debug("  package: %s" % (self.package))
        logger.debug("  basedir: %s" % (self.basedir))


class RuntimeConf(object):
    """Runtime configuration class common to all Fatbuildr applications."""

    def __init__(self):
        self.dirs = RuntimeSubConfDirs()
        self.images = RuntimeSubConfImages()
        self.config = None

    def load(self):
        """Load configuration files and set runtime parameters accordingly."""
        self.config = configparser.ConfigParser()
        # read vendor configuration file and override with site specific
        # configuration file
        vendor_conf_path = '/usr/lib/fatbuildr/fatbuildr.ini'
        site_conf_path = '/etc/fatbuildr/fatbuildr.ini'
        logger.debug("Loading vendor configuration file %s" % (vendor_conf_path))
        self.config.read_file(open(vendor_conf_path))
        logger.debug("Loading site specific configuration file %s" % (site_conf_path))
        self.config.read_file(open(site_conf_path))
        self.dirs.load(self.config)
        self.images.load(self.config)

    def dump(self):
        self.dirs.dump()
        self.images.dump()


class RuntimeConfCtl(RuntimeConf):
    """Runtime configuration class for FatbuildrCtl application."""

    def __init__(self):
        super().__init__()
        self.ctl = RuntimeSubConfCtl()

    def dump(self):
        """Dump all runtime configuration parameters when in debug mode."""
        if not logger.isEnabledFor(logging.DEBUG):
            return
        super().dump()
        self.ctl.dump()

    def load(self):
        super().load()
        self.ctl.load(self.config)
