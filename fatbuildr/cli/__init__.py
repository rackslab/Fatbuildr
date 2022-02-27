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

import sys
import atexit

from ..cleanup import CleanupRegistry
from ..log import logr

logger = logr(__name__)


class FatbuildrCliRun(object):
    @classmethod
    def run(cls):
        """Instanciate and execute the CliRun."""
        atexit.register(CleanupRegistry.clean)
        run = cls()

    def load_conf(self):

        try:
            self.conf.load()  # load configuration file
        except ValueError as err:
            logger.error("Error while loading configuration: %s" % (err))
            sys.exit(1)
