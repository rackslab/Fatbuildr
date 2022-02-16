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

from . import (
    REGISTER,
    BUS,
    DbusInstance,
    DbusSubmittedBuild,
    DbusRunningBuild,
    DbusArchivedBuild,
    DbusArtefact,
    DbusChangelogEntry,
    ErrorNoRunningBuild,
)
from ...log import logr

logger = logr(__name__)


@dbus_interface(REGISTER.interface_name)
class FatbuildrInterface(InterfaceTemplate):
    """The DBus interface of Fatbuildr."""

    def Instance(self, instance: Str) -> Structure:
        """Returns the instance user id."""
        return DbusInstance.to_structure(self.implementation.instance(instance))

    def PipelinesFormats(self, instance: Str) -> List[Str]:
        """Returns the list of formats defined in pipelines of the given instance."""
        return self.implementation.pipelines_formats(instance)

    def PipelinesFormatDistributions(
        self, instance: Str, format: Str
    ) -> List[Str]:
        """Returns the distributions of the given format in the pipelines of the instance."""
        return self.implementation.pipelines_format_distributions(
            instance, format
        )

    def PipelinesDistributionFormat(
        self, instance: Str, distribution: Str
    ) -> Str:
        """Returns the format of the given distribution in the pipelines of the instance."""
        return self.implementation.pipelines_distribution_format(
            instance, distribution
        )

    def PipelinesDistributionEnvironment(
        self, instance: Str, distribution: Str
    ) -> Str:
        """Returns the environment of the given distribution in the pipelines of the instance."""
        env = self.implementation.pipelines_distribution_environment(
            instance, distribution
        )
        if not env:
            return 'none'
        return env

    def PipelinesDistributionDerivatives(
        self, instance: Str, distribution: Str
    ) -> List[Str]:
        """Returns the derivatives of the given distribution in the pipelines of the instance."""
        return self.implementation.pipelines_distribution_derivatives(
            instance, distribution
        )

    def PipelinesDerivativeFormats(
        self, instance: Str, derivative: Str
    ) -> List[Str]:
        """Returns the formats of the given derivative in the pipelines of the instance."""
        return self.implementation.pipelines_derivative_formats(
            instance, derivative
        )

    @property
    def RegistryInstances(self) -> List[Str]:
        """The list of available instances."""
        return self.implementation.registry_instances

    def Queue(self, instance: Str) -> List[Structure]:
        """The list of builds in queue."""
        return DbusSubmittedBuild.to_structure_list(
            self.implementation.queue(instance)
        )

    def Running(self, instance: Str) -> Structure:
        """The currently running build"""
        return DbusRunningBuild.to_structure(
            self.implementation.running(instance)
        )

    def Archives(self, instance: Str) -> List[Structure]:
        """The list of builds in queue."""
        return DbusArchivedBuild.to_structure_list(
            self.implementation.archives(instance)
        )

    def Formats(self, instance: Str) -> List[Str]:
        """The list of available formats in an instance registries."""
        return self.implementation.formats(instance)

    def Distributions(self, instance: Str, fmt: Str) -> List[Str]:
        """The list of available distributions for a format in an instance
        registries."""
        return self.implementation.distributions(instance, fmt)

    def Derivatives(
        self, instance: Str, fmt: Str, distribution: Str
    ) -> List[Str]:
        """The list of available derivatives for a distribution in an instance
        registries."""
        return self.implementation.derivatives(instance, fmt, distribution)

    def Artefacts(
        self,
        instance: Str,
        fmt: Str,
        distribution: Str,
        derivative: Str,
    ) -> List[Structure]:
        """The artefacts in this derivative of this distribution registry."""
        return DbusArtefact.to_structure_list(
            self.implementation.artefacts(
                instance, fmt, distribution, derivative
            )
        )

    def ArtefactBinaries(
        self,
        instance: Str,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        src_artefact: Str,
    ) -> List[Structure]:
        """Return the list of binary artefacts generated by the given source
        artefact in this derivative of this distribution registry."""
        return DbusArtefact.to_structure_list(
            self.implementation.artefact_bins(
                instance, fmt, distribution, derivative, src_artefact
            )
        )

    def ArtefactSource(
        self,
        instance: Str,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        bin_artefact: Str,
    ) -> Structure:
        """Return the source artefact that generated by the given binary
        artefact in this derivative of this distribution registry."""
        return DbusArtefact.to_structure(
            self.implementation.artefact_src(
                instance, fmt, distribution, derivative, bin_artefact
            )
        )

    def Changelog(
        self,
        instance: Str,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        architecture: Str,
        artefact: Str,
    ) -> List[Structure]:
        """Return the list of changelog entries of the the given artefact and
        architecture in this derivative of this distribution registry."""
        return DbusChangelogEntry.to_structure_list(
            self.implementation.changelog(
                instance, fmt, distribution, derivative, architecture, artefact
            )
        )

    def Submit(self, instance: Str, input: Str) -> Str:
        """Submit a new build."""
        return self.implementation.submit(instance, input)

    def KeyringExport(self, instance: Str) -> Str:
        """Returns armored public key of instance keyring."""
        return self.implementation.keyring_export(instance)


class FatbuildrMultiplexer(object):
    """The implementation of Fatbuildr Manager."""

    def __init__(self, instances, registry_mgr, keyring_mgr, timer):
        self.instances = instances
        self.registry_mgr = registry_mgr
        self.keyring_mgr = keyring_mgr
        self.timer = timer

    def instance(self, instance: Str):
        self.timer.reset()
        return DbusInstance.load_from_instance(self.instances[instance])

    def pipelines_formats(self, instance: Str):
        self.timer.reset()
        return self.instances[instance].pipelines.formats

    def pipelines_format_distributions(self, instance: Str, format: Str):
        self.timer.reset()
        return self.instances[instance].pipelines.format_dists(format)

    def pipelines_distribution_format(self, instance: Str, distribution: Str):
        self.timer.reset()
        return self.instances[instance].pipelines.dist_format(distribution)

    def pipelines_distribution_derivatives(
        self, instance: Str, distribution: Str
    ):
        self.timer.reset()
        return self.instances[instance].pipelines.dist_derivatives(distribution)

    def pipelines_distribution_environment(
        self, instance: Str, distribution: Str
    ):
        self.timer.reset()
        return self.instances[instance].pipelines.dist_env(distribution)

    def pipelines_derivative_formats(self, instance: Str, derivative: Str):
        self.timer.reset()
        return self.instances[instance].pipelines.derivative_formats(derivative)

    @property
    def registry_instances(self):
        self.timer.reset()
        return self.registry_mgr.instances

    def queue(self, instance):
        """The list of builds in instance queue."""
        self.timer.reset()
        return [
            DbusSubmittedBuild.load_from_build(_build)
            for _build in self.instances[instance].build_mgr.queue.dump()
        ]

    def running(self, instance):
        """The list of builds in queue."""
        self.timer.reset()
        if not self.instances[instance].build_mgr.running:
            raise ErrorNoRunningBuild()
        return DbusRunningBuild.load_from_build(
            self.instances[instance].build_mgr.running
        )

    def archives(self, instance):
        """The list of archived builds."""
        self.timer.reset()
        return [
            DbusArchivedBuild.load_from_build(_build)
            for _build in self.instances[instance].build_mgr.archives()
        ]

    def formats(self, instance: Str):
        self.timer.reset()
        return self.registry_mgr.formats(instance)

    def distributions(self, instance: Str, fmt: Str):
        self.timer.reset()
        return self.registry_mgr.distributions(instance, fmt)

    def derivatives(self, instance: Str, fmt: Str, distribution: Str):
        self.timer.reset()
        return self.registry_mgr.derivatives(instance, fmt, distribution)

    def artefacts(
        self, instance: Str, fmt: Str, distribution: Str, derivative: Str
    ):
        """Get all artefacts in this derivative of this distribution registry."""
        self.timer.reset()
        artefacts = self.registry_mgr.artefacts(
            instance, fmt, distribution, derivative
        )
        return [
            DbusArtefact.load_from_artefact(artefact) for artefact in artefacts
        ]

    def artefact_bins(
        self,
        instance: Str,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        src_artefact: Str,
    ):
        """Get all binary artefacts generated by the given source artefact in
        this derivative of this distribution registry."""
        self.timer.reset()
        artefacts = self.registry_mgr.artefact_bins(
            instance, fmt, distribution, derivative, src_artefact
        )
        return [
            DbusArtefact.load_from_artefact(artefact) for artefact in artefacts
        ]

    def artefact_src(
        self,
        instance: Str,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        bin_artefact: Str,
    ):
        """Get the source artefact that generated by the given binary artefact
        in this distribution registry."""
        self.timer.reset()
        artefact = self.registry_mgr.artefact_src(
            instance, fmt, distribution, derivative, bin_artefact
        )
        return DbusArtefact.load_from_artefact(artefact)

    def changelog(
        self,
        instance: Str,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        architecture: Str,
        artefact: Str,
    ):
        """Get the changelog of the given artefact and architecture in this
        distribution registry."""
        self.timer.reset()
        changelog = self.registry_mgr.changelog(
            instance, fmt, distribution, derivative, architecture, artefact
        )
        return [
            DbusChangelogEntry.load_from_entry(entry) for entry in changelog
        ]

    def submit(self, instance: Str, input: Str):
        """Submit a new build."""
        self.timer.reset()
        submission = self.instances[instance].build_mgr.submit(input)
        return submission.id

    def keyring_export(self, instance: Str):
        """Returns armored public key of instance keyring."""
        self.timer.reset()
        return self.keyring_mgr.keyring(instance).export()


class DbusServer(object):
    def run(self, instances, registry_mgr, keyring_mgr, timer):

        # Print the generated XML specification.
        logger.debug(
            "Dbus service interface generated:\n %s",
            XMLGenerator.prettify_xml(FatbuildrInterface.__dbus_xml__),
        )

        # Create the Fatbuildr multiplexer.
        multiplexer = FatbuildrMultiplexer(
            instances, registry_mgr, keyring_mgr, timer
        )

        # Publish the register at /org/rackslab/Fatbuildr.
        BUS.publish_object(
            REGISTER.object_path, FatbuildrInterface(multiplexer)
        )

        # Register the service name org.rackslab.Fatbuildr.
        BUS.register_service(REGISTER.service_name)

        # Start the event loop.
        self.loop = EventLoop()
        self.loop.run()

    def quit(self):
        self.loop.quit()
