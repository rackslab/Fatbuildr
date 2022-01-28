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

from . import FatbuildrCliRun
from ..version import __version__
from ..conf import RuntimeConfd
from ..builds.manager import ServerBuildsManager
from ..protocols import ServerFactory
from ..timer import ServerTimer
from ..services import ServiceManager
from ..registry.manager import RegistryManager
from ..log import logr

logger = logr(__name__)


class Fatbuildrd(FatbuildrCliRun):

    def __init__(self):
        super().__init__()

        parser = argparse.ArgumentParser(description='Do something with fatbuildr.')
        parser.add_argument('-v', '--version', dest='version', action='version', version='%(prog)s ' + __version__)
        parser.add_argument('--debug', dest='debug', action='store_true', help="Enable debug mode")

        args = parser.parse_args()

        logger.setup(args.debug)

        self.conf = RuntimeConfd()
        self.load()
        self._run()

    def load(self):
        super().load()

        # set debug level on root logger if set in conf file
        if self.conf.run.debug:
            logger.ensure_debug()

        self.conf.dump()

    def _run(self):

        logger.debug("Running fatbuildrd")
        self.build_mgr = ServerBuildsManager(self.conf)
        self.registry_mgr = RegistryManager(self.conf)
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
        self.build_mgr.clear_orphaned()

        while True:
            try:
                # pick the first request in queue
                build = self.build_mgr.pick(self.timer.remaining)
                if build:
                    self.timer.lock()  # lock the timer while builds are in the queue
                    build.run()
                    self.build_mgr.archive(build)
            except RuntimeError as err:
                logger.error("Error while processing build: %s" % (err))
            if self.build_mgr.queue.empty():
                self.timer.release()  # allow threads to leave
            if self.timer.over:
                break
        logger.info("Stopping builder thread as timer is over and build queue "
                    "is empty")

    def _server(self):
        """Thread handling requests from clients."""
        logger.info("Starting server thread")
        self.server = ServerFactory.get()
        self.server.run(self.build_mgr, self.registry_mgr, self.timer)
        logger.info("Stopping server thread")

    def _timer(self):
        logger.info("Starting timer thread")
        while not self.timer.over:
            # notify service manager watchdog fatbuildrd is alive
            self.sm.notify_watchdog()
            self.timer.wait(timeout=10)

        logger.info("Timer is over, stopping timer thread")
        self.server.quit()
