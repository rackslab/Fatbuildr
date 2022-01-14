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

import argparse
import sys
import logging

from . import FatbuildrCliRun
from ..version import __version__
from ..conf import RuntimeConfd
from ..builds.manager import BuildsManager

logger = logging.getLogger(__name__)

class Fatbuildrd(FatbuildrCliRun):

    def __init__(self):
        super().__init__()

        parser = argparse.ArgumentParser(description='Do something with fatbuildr.')
        parser.add_argument('-v', '--version', dest='version', action='version', version='%(prog)s ' + __version__)
        parser.add_argument('--debug', dest='debug', action='store_true', help="Enable debug mode")

        args = parser.parse_args()

        # setup logger according to args
        if args.debug:
            logging_level = logging.DEBUG
        else:
            logging_level = logging.INFO
        logging.basicConfig(level=logging_level)

        self.conf = RuntimeConfd()
        self.load()
        self._run()

    def load(self):
        super().load()

        # set debug level on root logger if set in conf file
        if self.conf.run.debug:
            logging.getLogger().setLevel(level=logging.DEBUG)

        self.conf.dump()

    def _run(self):
        logger.debug("Running fatbuildrd")
        mgr = BuildsManager(self.conf)

        mgr.clear_orphaned()

        while not mgr.empty:
            try:
                # pick the first request in queue
                build = mgr.pick()
                build.run()
                mgr.archive(build)
            except SystemError as err:
                logger.error("Error while processing build: %s" % (err))
                sys.exit(1)
        logger.info("No build request available in queue, leaving")
