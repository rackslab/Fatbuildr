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

import shutil
import os
import logging

logger = logging.getLogger(__name__)


class CleanupRegistry(object):
    """Registry of things to cleanup before leaving Fatbuildr apps"""
    _tmpdirs = []

    @classmethod
    def add_tmpdir(cls, tmpdir):
        logger.debug("Registering tmpdir %s" % (tmpdir))
        cls._tmpdirs.append(tmpdir)

    @classmethod
    def del_tmpdir(cls, tmpdir):
        logger.debug("Unregistering tmpdir %s" % (tmpdir))
        cls._tmpdirs.remove(tmpdir)

    @classmethod
    def clean(cls):
        for _dir in cls._tmpdirs:
            if os.path.exists(_dir):
                logger.debug("Removing temporary directory %s" % (_dir))
                shutil.rmtree(_dir)
            else:
                logger.warning("Temporary directory %s registered for removal does not exist" % (_dir))
