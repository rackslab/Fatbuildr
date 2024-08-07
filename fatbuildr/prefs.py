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
from pathlib import Path
import os

from .log import logr

logger = logr(__name__)


def default_user_pref():
    """Returns the default path to the user preferences file, through
    XDG_CONFIG_HOME environment variable if it is set."""
    return Path(os.getenv('XDG_CONFIG_HOME', '~/.config')).joinpath(
        'fatbuildr.ini'
    )


def default_user_tokens_dir():
    """Returns the default path to the user tokens directory, through
    XDG_DATA_HOME environment variable if it is set."""
    return Path(os.getenv('XDG_DATA_HOME', '~/.local/share')).joinpath(
        'fatbuildr'
    )


def default_commit_message_template():
    return Path('/usr/share/fatbuildr/commit-message-template')


class UserPreferences:
    DEFAULT = default_user_pref()

    def __init__(self, path):

        self.user_name = None
        self.user_email = None
        self.uri = None
        self.basedir = None
        self.message = None
        self.tokens_dir = default_user_tokens_dir()
        self.commit_message_template = default_commit_message_template()

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

        basedir = config.get('prefs', 'basedir', fallback=None)
        if basedir:
            basedir = Path(basedir).expanduser()
        self.basedir = basedir
        self.message = config.get('prefs', 'message', fallback=None)
        self.tokens_dir = Path(
            config.get(
                'prefs',
                'tokens',
                fallback=default_user_tokens_dir(),
            )
        ).expanduser()
        self.commit_message_template = Path(
            config.get(
                'prefs',
                'commit_template',
                fallback=default_commit_message_template(),
            )
        ).expanduser()

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
        logger.debug("   tokens: %s", self.tokens_dir)
