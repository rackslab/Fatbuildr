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

from dasbus.loop import EventLoop
from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.server.template import InterfaceTemplate
from dasbus.signal import Signal
from dasbus.typing import Structure, List, Str
from dasbus.xml import XMLGenerator

from . import REGISTER, BUS, DbusSubmittedBuild, DbusRunningBuild, DbusArchivedBuild, ErrorNoRunningBuild
from ...log import logr

logger = logr(__name__)


@dbus_interface(REGISTER.interface_name)
class FatbuildrInterface(InterfaceTemplate):
    """The DBus interface of Fatbuildr."""

    @property
    def Queue(self) -> List[Structure]:
        """The list of builds in queue."""
        return DbusSubmittedBuild.to_structure_list(self.implementation.queue)

    @property
    def Running(self) -> Structure:
        """The currently running build"""
        return DbusRunningBuild.to_structure(self.implementation.running)

    @property
    def Archives(self) -> List[Structure]:
        """The list of builds in queue."""
        return DbusArchivedBuild.to_structure_list(self.implementation.archives)

    def Submit(self, input: Str) -> Str:
        """Submit a new build."""
        return self.implementation.submit(input)


class FatbuildrMultiplexer(object):
    """The implementation of Fatbuildr Manager."""

    def __init__(self, mgr, timer):
        self.mgr = mgr
        self.timer = timer

    @property
    def queue(self):
        """The list of builds in queue."""
        self.timer.reset()
        return [DbusSubmittedBuild.load_from_build(_build)
                for _build in self.mgr.queue.dump()]

    @property
    def running(self):
        """The list of builds in queue."""
        self.timer.reset()
        if not self.mgr.running:
            raise ErrorNoRunningBuild()
        return DbusRunningBuild.load_from_build(self.mgr.running)

    @property
    def archives(self):
        """The list of archived builds."""
        self.timer.reset()
        return [DbusArchivedBuild.load_from_build(_build)
                for _build in self.mgr.archives()]

    def submit(self, input: Str):
        """Submit a new build."""
        self.timer.reset()
        submission = self.mgr.submit(input)
        return submission.id


class DbusServer(object):

    def run(self, mgr, timer):

        # Print the generated XML specification.
        logger.debug("Dbus service interface generated:\n %s",
                     XMLGenerator.prettify_xml(FatbuildrInterface.__dbus_xml__))

        # Create the Fatbuildr multiplexer.
        multiplexer = FatbuildrMultiplexer(mgr, timer)

        # Publish the register at /org/rackslab/Fatbuildr/Builds.
        BUS.publish_object(
            REGISTER.object_path,
            FatbuildrInterface(multiplexer)
        )

        # Register the service name org.rackslab.Fatbuildr.Builds.
        BUS.register_service(
            REGISTER.service_name
        )

        # Start the event loop.
        self.loop = EventLoop()
        self.loop.run()

    def quit(self):
        self.loop.quit()
