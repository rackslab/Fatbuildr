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
import shutil
import time

from . import FatbuildrCliRun
from ..version import __version__
from ..conf import RuntimeConfd
from ..protocols.crawler import register_protocols
from ..protocols import ServerFactory
from ..instances import Instances
from ..timer import ServerTimer
from ..services import ServiceManager
from ..errors import FatbuildrRuntimeError
from ..log import logr

logger = logr(__name__)


class Fatbuildrd(FatbuildrCliRun):
    def __init__(self):
        parser = argparse.ArgumentParser(
            description='Do something with fatbuildr.'
        )
        parser.add_argument(
            '-v',
            '--version',
            dest='version',
            action='version',
            version='%(prog)s ' + __version__,
        )
        parser.add_argument(
            '--debug',
            dest='debug',
            action='store_true',
            help="Enable debug mode",
        )

        args = parser.parse_args()

        logger.setup(args.debug, fulldebug=False)

        self.conf = RuntimeConfd()
        self.instances = None  # initialized in load(), after conf is loaded

        self.load()

        self._run()

    def load(self):
        super().load_conf()

        # set debug level on root logger if set in conf file
        if self.conf.run.debug or self.conf.run.fulldebug:
            logger.ensure_debug()

        if self.conf.run.fulldebug:
            logger.ensure_fulldebug()

        self.conf.dump()
        self.instances = Instances(self.conf)
        self.instances.load()

    def _run(self):

        logger.debug("Running fatbuildrd")
        self.server = None
        self.sm = ServiceManager()
        self.timer = ServerTimer()

        self.clear_orphaned_builds()
        # load all tasks and exportable types structures in protocol
        register_protocols()

        self.workers = {}
        for instance in self.instances:
            self.workers[instance.id] = threading.Thread(
                target=self._worker,
                args=(instance,),
                name=f"worker-{instance.id}",
            )
            self.workers[instance.id].start()

        server_thread = threading.Thread(target=self._server, name='server')
        server_thread.start()

        timer_thread = threading.Thread(target=self._timer, name='timer')
        timer_thread.start()

        logger.debug("All threads are started")

        for instance, thread in self.workers.items():
            thread.join()
        server_thread.join()
        timer_thread.join()

        logger.debug("All threads are properly stopped")

    def _worker(self, instance):
        """Thread working over an instance tasks queue."""

        logger.info("Starting worker thread for instance %s", instance.id)

        timer_inc = False
        while True:
            try:
                # Try picking the first request in queue for 60 seconds. The
                # timeout is set to 60 seconds to avoid too frequent polling
                # but it can be interrupted by the timer thread when it leaves.
                task = instance.tasks_mgr.pick(60)
                if task:
                    # lock the timer while tasks are in the queue
                    self.timer.register_worker(instance.id)
                    instance.tasks_mgr.run(task)
            except FatbuildrRuntimeError as err:
                logger.error("Error while processing task: %s", err)
            if instance.tasks_mgr.queue.empty():
                # If the queue is empty, wait for extra seconds in case a
                # client submits successive tasks (ie. it waits for one task to
                # finish before sending the following). If the queue is still
                # empty after these extra seconds, we can consider the worker
                # can release the timer and leave safely. If we release the
                # timer right after finishing the last task, the client
                # submitting successive tasks would trigger useless fatbuildrd
                # stop/start.
                logger.debug("Giving grace time before releasing timer")
                time.sleep(3)
            if instance.tasks_mgr.queue.empty():
                # release the timer to allow other threads to leave
                self.timer.unregister_worker(instance.id)
            if self.timer.over:
                break
        logger.info(
            f"Stopping worker thread for instance {instance.id} as timer is "
            "over and task queue is empty"
        )

    def _server(self):
        """Thread handling requests from clients."""
        logger.info("Starting server thread")
        self.server = ServerFactory.get()
        self.server.run(
            self.instances,
            self.timer,
        )
        logger.info("Stopping server thread")

    def _timer(self):
        logger.info("Starting timer thread")
        while not self.timer.over:
            stateok = True
            for instance, thread in self.workers.items():
                if not thread.is_alive():
                    logger.warning(
                        "Detected dead %s thread, notifying service manager",
                        thread.name,
                    )
                    stateok = False
                    self.sm.set_status(f"Worker thread {thread.name} failed")
                    self.sm.notify_error()
            if stateok:
                # If state is OK, notify service manager watchdog fatbuildrd is
                # alive.
                self.sm.notify_watchdog()
            self.timer.wait(timeout=10)

        logger.info("Timer is over")

        # Tell the service manager the daemon is preparing to stop so it can
        # inform users the real internal service stopping state.
        self.sm.notify_stop()

        logger.info("Stopping the server thread")
        # First stop server thread to avoid clients from submitting new tasks
        self.server.quit()

        logger.info("Notifying all worker threads to stop")
        for instance in self.instances:
            with instance.tasks_mgr.queue._count._cond:
                logger.debug(
                    "Interrupting %s instance tasks manager to stop waiting "
                    "for tasks",
                    instance.id,
                )
                instance.tasks_mgr.interrupt()
        logger.info("Leaving timer thread")

    def clear_orphaned_builds(self):
        """Remove all build directories in queue directory."""
        for build_path in self.conf.dirs.queue.iterdir():
            logger.warning("Removing orphaned build %s", build_path.name)
            shutil.rmtree(build_path)
