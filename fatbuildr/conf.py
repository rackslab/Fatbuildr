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
import re
from pathlib import Path

from .log import logr

logger = logr(__name__)


class RuntimeSubConfDirs(object):
    """Runtime sub-configuration class to hold directories paths."""

    def __init__(self):

        self.instances = None
        self.queue = None
        self.archives = None
        self.registry = None
        self.cache = None
        self.tmp = None

    def load(self, config):
        section = 'dirs'
        self.instances = Path(config.get(section, 'instances'))
        self.queue = Path(config.get(section, 'queue'))
        self.archives = Path(config.get(section, 'archives'))
        self.registry = Path(config.get(section, 'registry'))
        self.cache = Path(config.get(section, 'cache'))
        self.tmp = Path(config.get(section, 'tmp'))

    def dump(self):
        logger.debug("[dirs]")
        logger.debug("  instances: %s", self.instances)
        logger.debug("  queue: %s", self.queue)
        logger.debug("  archives: %s", self.archives)
        logger.debug("  registry: %s", self.registry)
        logger.debug("  cache: %s", self.cache)
        logger.debug("  tmp: %s", self.tmp)


class RuntimeSubConfImages(object):
    """Runtime sub-configuration class to hold images settings."""

    def __init__(self):

        self.storage = None
        self.defs = None
        self.formats = None
        self.create_cmd = None

    def load(self, config):
        section = 'images'
        self.storage = Path(config.get(section, 'storage'))
        self.defs = Path(config.get(section, 'defs'))
        self.formats = config.get(section, 'formats').split(',')
        self.create_cmd = config.get(section, 'create_cmd')

    def dump(self):
        logger.debug("[images]")
        logger.debug("  storage: %s", self.storage)
        logger.debug("  defs: %s", self.defs)
        logger.debug("  create_cmd: %s", self.create_cmd)


class RuntimeSubConfRegistry(object):
    """Runtime sub-configuration class to hold registry settings."""

    def __init__(self):

        self.conf = None

    def load(self, config):
        section = 'registry'
        self.conf = Path(config.get(section, 'conf'))

    def dump(self):
        logger.debug("[registry]")
        logger.debug("  conf: %s", self.conf)


class RuntimeSubConfContainers(object):
    """Runtime sub-configuration class to hold containers settings."""

    def __init__(self):

        self.exec = None
        self.init_opts = None
        self.opts = None

    def load(self, config):
        section = 'containers'
        self.exec = Path(config.get(section, 'exec'))
        # replace empty value by None for better semantic
        _init_opts = config.get(section, 'init_opts')
        if _init_opts == '':
            self.init_opts = None
        else:
            self.init_opts = _init_opts.split(' ')
        _opts = config.get(section, 'opts')
        if _opts == '':
            self.opts = None
        else:
            self.opts = _opts.split(' ')

    def dump(self):
        logger.debug("[containers]")
        logger.debug("  exec: %s", self.exec)
        logger.debug("  init_opts: %s", self.init_opts)
        logger.debug("  opts: %s", self.opts)


class RuntimeSubConfKeyring(object):
    """Runtime sub-configuration class to hold keyring settings."""

    def __init__(self):

        self.storage = None
        self.type = None
        self.size = None
        self.expires = None

    def _parse_duration(self, _expires):
        m = re.search(r'(\d+)([a-z])', _expires)
        quantity = int(m.group(1))
        unit = m.group(2)
        if unit == 'd':
            self.expires = quantity * 86400
        elif unit == 'm':
            self.expires = quantity * 86400 * 30
        elif unit == 'y':
            self.expires = quantity * 86400 * 365
        else:
            raise ValueError(f"keyring expires unit '{unit}' is not valid")

    def load(self, config):
        section = 'keyring'
        self.storage = Path(config.get(section, 'storage'))
        self.type = config.get(section, 'type')
        self.size = config.getint(section, 'size')
        try:
            self.expires = config.getboolean(section, 'expires')
        except ValueError:
            _expires = config.get(section, 'expires')
            self._parse_duration(_expires)
        if self.expires == True:
            raise ValueError(
                "keyring expires must be set with a duration to be enabled"
            )

    def dump(self):
        logger.debug("[keyring]")
        logger.debug("  storage: %s", self.storage)
        logger.debug("  type: %s", self.type)
        logger.debug("  size: %s", self.size)
        logger.debug("  expires: %s", str(self.expires))


class RuntimeSubConfFormatDeb(object):
    """Runtime sub-configuration class to hold Deb format settings."""

    def __init__(self):

        self.env_path = None
        self.init_cmd = None
        self.img_update_cmds = None
        self.env_update_cmds = None
        self.prescript_deps = []

    def load(self, config):
        section = 'format:deb'
        self.env_path = config.get(section, 'env_path')
        self.init_cmd = config.get(section, 'init_cmd')
        self.img_update_cmds = config.get(section, 'img_update_cmds')
        self.env_update_cmds = config.get(section, 'env_update_cmds')
        self.prescript_deps = config.get(section, 'prescript_deps').split(' ')

    def dump(self):
        logger.debug("[format:deb]")
        logger.debug("  env_path: %s", self.env_path)
        logger.debug("  init_cmd: %s", self.init_cmd)
        logger.debug("  img_update_cmds: %s", self.img_update_cmds)
        logger.debug("  env_update_cmds: %s", self.env_update_cmds)
        logger.debug("  prescript_deps: %s", self.prescript_deps)


class RuntimeSubConfFormatRpm(object):
    """Runtime sub-configuration class to hold RPM format settings."""

    def __init__(self):

        self.env_path = None
        self.init_cmd = None
        self.img_update_cmds = None
        self.env_update_cmds = None
        self.prescript_deps = []

    def load(self, config):
        section = 'format:rpm'
        self.env_path = config.get(section, 'env_path')
        self.init_cmd = config.get(section, 'init_cmd')
        self.img_update_cmds = config.get(section, 'img_update_cmds')
        self.env_update_cmds = config.get(section, 'env_update_cmds')
        self.prescript_deps = config.get(section, 'prescript_deps').split(' ')

    def dump(self):
        logger.debug("[format:rpm]")
        logger.debug("  env_path: %s", self.env_path)
        logger.debug("  init_cmd: %s", self.init_cmd)
        logger.debug("  img_update_cmds: %s", self.img_update_cmds)
        logger.debug("  env_update_cmds: %s", self.env_update_cmds)
        logger.debug("  prescript_deps: %s", self.prescript_deps)


class RuntimeSubConfFormatOsi(object):
    """Runtime sub-configuration class to hold RPM format settings."""

    def __init__(self):

        self.init_cmd = None
        self.img_update_cmds = None

    def load(self, config):
        section = 'format:osi'
        self.img_update_cmds = config.get(section, 'img_update_cmds')

    def dump(self):
        logger.debug("[format:osi]")
        logger.debug("  img_update_cmds: %s", self.img_update_cmds)


class RuntimeConfApp(object):
    """Runtime sub-configuration class common to all Fatbuildr applications."""

    def __init__(self):
        pass


class RuntimeSubConfd(RuntimeConfApp):
    """Runtime sub-configuration class to fatbuildrd parameters."""

    def __init__(self):
        super().__init__()
        self.debug = None
        self.fulldebug = None

    def load(self, config):
        section = 'daemon'
        self.debug = config.getboolean('daemon', 'debug')
        self.fulldebug = config.getboolean('daemon', 'fulldebug')

    def dump(self):
        logger.debug("[daemon]")
        logger.debug("  debug: %s", self.debug)
        logger.debug("  fulldebug: %s", self.fulldebug)


class RuntimeSubConfWeb(RuntimeConfApp):
    """Runtime sub-configuration class to fatbuildrWeb parameters."""

    def __init__(self):
        super().__init__()
        self.debug = None
        self.host = None
        self.port = None
        self.vendor_templates = None
        self.templates = None
        self.static = None

    def load(self, config):
        section = 'web'
        self.debug = config.getboolean(section, 'debug')
        self.host = config.get(section, 'host')
        self.port = config.getint(section, 'port')
        self.vendor_templates = config.get(section, 'vendor_templates')
        self.templates = config.get(section, 'templates')
        self.static = config.get(section, 'static')

    def dump(self):
        logger.debug("[web]")
        logger.debug("  debug: %s", self.debug)
        logger.debug("  host: %s", self.host)
        logger.debug("  port: %i", self.port)
        logger.debug("  vendor_templates: %s", self.vendor_templates)
        logger.debug("  static: %s", self.static)


class RuntimeConf(object):
    """Runtime configuration class common to all Fatbuildr applications."""

    def __init__(self, run):
        self.run = run
        self.dirs = RuntimeSubConfDirs()
        self.images = RuntimeSubConfImages()
        self.registry = RuntimeSubConfRegistry()
        self.containers = RuntimeSubConfContainers()
        self.keyring = RuntimeSubConfKeyring()
        self.deb = RuntimeSubConfFormatDeb()
        self.rpm = RuntimeSubConfFormatRpm()
        self.osi = RuntimeSubConfFormatOsi()
        self.config = None

    def load(self):
        """Load configuration files and set runtime parameters accordingly."""
        self.config = configparser.ConfigParser()
        # read vendor configuration file and override with site specific
        # configuration file
        vendor_conf_path = '/usr/lib/fatbuildr/fatbuildr.ini'
        site_conf_path = '/etc/fatbuildr/fatbuildr.ini'
        logger.debug("Loading vendor configuration file %s", vendor_conf_path)
        self.config.read_file(open(vendor_conf_path))
        logger.debug(
            "Loading site specific configuration file %s", site_conf_path
        )
        self.config.read_file(open(site_conf_path))
        self.run.load(self.config)
        self.dirs.load(self.config)
        self.images.load(self.config)
        self.registry.load(self.config)
        self.containers.load(self.config)
        self.keyring.load(self.config)
        self.deb.load(self.config)
        self.rpm.load(self.config)
        self.osi.load(self.config)

    def dump(self):
        """Dump all runtime configuration parameters when in debug mode."""
        if not logger.has_debug():
            return
        self.run.dump()
        self.dirs.dump()
        self.images.dump()
        self.registry.dump()
        self.containers.dump()
        self.keyring.dump()
        self.deb.dump()
        self.rpm.dump()
        self.osi.dump()


class RuntimeConfd(RuntimeConf):
    """Runtime configuration class for Fatbuildrd application."""

    def __init__(self):
        super().__init__(RuntimeSubConfd())


class RuntimeConfWeb(RuntimeConf):
    """Runtime configuration class for FatbuildrWeb application."""

    def __init__(self):
        super().__init__(RuntimeSubConfWeb())
