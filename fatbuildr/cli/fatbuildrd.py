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
import threading
import logging

from . import FatbuildrCliRun
from ..version import __version__
from ..conf import RuntimeConfd
from ..builds.manager import ServerBuildsManager
from ..protocols import ServerFactory
from ..timer import ServerTimer
from ..services import ServiceManager

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

        _root_logger = logging.getLogger()
        _root_logger.setLevel(logging_level)
        handler = logging.StreamHandler()
        handler.setLevel(logging_level)
        formatter = logging.Formatter('%(threadName)s: [%(levelname)s] %(message)s')
        handler.setFormatter(formatter)
        _root_logger.addHandler(handler)

        self.conf = RuntimeConfd()
        self.load()
        self._run()

    def load(self):
        super().load()

        # set debug level on root logger if set in conf file
        if self.conf.run.debug:
            _root_logger = logging.getLogger()
            _root_logger.setLevel(level=logging.DEBUG)
            for handler in _root_logger.handlers:
                handler.setLevel(logging.DEBUG)

        self.conf.dump()

    def _run(self):

        logger.debug("Running fatbuildrd")
        self.mgr = ServerBuildsManager(self.conf)
        self.server = None
        self.sm = ServiceManager()
        self.timer = ServerTimer()

        builder_thread = threading.Thread(target=self._builder, name='builder')
        builder_thread.start()

        server_thread = threading.Thread(target=self._server, name='server')
        server_thread.start()

        timer_thread = threading.Thread(target=self._timer, name='timer')
        timer_thread.start()

        logger.debug("All threads are started")

        builder_thread.join()
        server_thread.join()
        timer_thread.join()

        logger.debug("All threads are properly stopped")
        self.sm.notify_stop()

    def _builder(self):
        """Thread handling build loop."""
        logger.info("Starting builder thread")
        self.mgr.clear_orphaned()

        while not self.timer.over:
            try:
                # pick the first request in queue
                build = self.mgr.pick(self.timer.remaining)
                if build:
                    build.run()
                    self.mgr.archive(build)
            except RuntimeError as err:
                logger.error("Error while processing build: %s" % (err))
        logger.info("Stopping builder thread as timer is over")

    def _server(self):
        """Thread handling requests from clients."""
        logger.info("Starting server thread")
        self.server = ServerFactory.get()
        self.server.run(self.mgr, self.timer)
        logger.info("Stopping server thread")

    def _timer(self):
        logger.info("Starting timer thread")
        while not self.timer.over:
            self.sm.notify_watchdog()
            logger.info("Waiting for %f" % (self.timer.remaining))
            self.timer.wait()

        logger.info("Timer is over, stopping server thread")
        self.server.quit()
