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

from .log import logr

logger = logr(__name__)


class UserPreferences:
    def __init__(self, path):

        self.user_name = None
        self.user_email = None
        self.uri = None
        self.basedir = None
        self.message = None

        if not path.expanduser().exists():
            logger.debug(
                "User preference file %s does not exist, no preferences loaded",
                path,
            )
            return

        config = configparser.ConfigParser()
        logger.debug("Loading user preferences file %s", path)
        config.read_file(open(path.expanduser()))

        self.user_name = config.get('user', 'name', fallback=None)
        self.user_email = config.get('user', 'email', fallback=None)
        self.uri = config.get('prefs', 'uri', fallback=None)
        self.basedir = config.get('prefs', 'basedir', fallback=None)
        self.message = config.get('prefs', 'message', fallback=None)

    def dump(self):
        if not logger.has_debug():
            return
        logger.debug("User preferences:")
        logger.debug(" [user]")
        logger.debug("   name: %s", self.user_name)
        logger.debug("   email: %s", self.user_email)
        logger.debug(" [prefs]")
        logger.debug("   uri: %s", self.uri)
        logger.debug("   basedir: %s", self.basedir)
        logger.debug("   message: %s", self.message)
