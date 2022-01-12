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
import threading
import logging

from . import FatbuildrCliRun
from ..version import __version__
from ..conf import RuntimeConfd
from ..builds.manager import BuildsManager
from ..protocols import ServerFactory

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
        self.mgr = BuildsManager(self.conf)

        builder_thread = threading.Thread(target=self._builder)
        builder_thread.start()

        server_thread = threading.Thread(target=self._server)
        server_thread.start()

        builder_thread.join()
        server_thread.join()

    def _builder(self):
        """Thread handling build loop."""
        logger.info("Starting builder thread")
        self.mgr.clear_orphaned()

        while True:
            try:
                # pick the first request in queue
                build = self.mgr.pick()
                if build:
                    build.run()
                    self.mgr.archive(build)
            except RuntimeError as err:
                logger.error("Error while processing build: %s" % (err))

    def _server(self):
        """Thread handling requests from clients."""
        logger.info("Starting server thread")
        server = ServerFactory.get()
        server.run(self.mgr)
