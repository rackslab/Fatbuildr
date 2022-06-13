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

import pwd

from dasbus.loop import EventLoop
from dasbus.server.interface import dbus_interface, accepts_additional_arguments
from dasbus.server.handler import ServerObjectHandler
from dasbus.server.property import emits_properties_changed
from dasbus.server.template import InterfaceTemplate
from dasbus.signal import Signal
from dasbus.typing import Structure, List, Str, Int, Bool, Variant
from dasbus.xml import XMLGenerator

from . import (
    FATBUILDR_SERVICE,
    BUS,
    DbusInstance,
    DbusRunnableTask,
    DbusArtifact,
    DbusChangelogEntry,
    DbusKeyring,
    ErrorNotAuthorized,
    ErrorNoRunningTask,
    ErrorNoKeyring,
    ErrorArtifactNotFound,
    valueornone,
)
from ...log import logr

logger = logr(__name__)


# Method attribute for the @accepts_additional_arguments decorator.
REQUIRE_POLKIT_AUTHORIZATION_ATTRIBUTE = (
    "__dbus_handler_require_polkit_authorization__"
)


def require_polkit_authorization(action):
    """Decorator for InterfaceTemplate methods to check for polkit authorization
    on the given action prior to running the method. The decorator actually
    defines an attribute on the method, this attribute is consumed by
    AuthorizationServerObjectHandler to actually ask polkit about the
    authorization on the action."""

    def wrap(method):
        setattr(method, REQUIRE_POLKIT_AUTHORIZATION_ATTRIBUTE, action)
        return method

    return wrap


class AuthorizationServerObjectHandler(ServerObjectHandler):
    """Child class of dasbus ServerObjectHandler just to override _handle_call()
    method."""

    def _handle_call(
        self, interface_name, method_name, *parameters, **additional_args
    ):
        """This method checks if the polkit authorization attribute has been
        defined on the method by @require_polkit_authorization decorator. In
        this case, it checks sender authorization on the associated action."""
        handler = self._find_handler(interface_name, method_name)

        action = getattr(handler, REQUIRE_POLKIT_AUTHORIZATION_ATTRIBUTE, None)
        if action:
            AuthorizationServerObjectHandler.check_auth(
                additional_args['call_info']['sender'], action
            )

        return super()._handle_call(
            interface_name, method_name, *parameters, **additional_args
        )

    @staticmethod
    def check_auth(sender, action):
        """This method asks polkit for given sender authorization on the given
        action. It raises ErrorNotAuthorized exception if the authorization
        fails."""
        proxy = BUS.get_proxy(
            "org.freedesktop.DBus", "/org/freedesktop/DBus/Bus"
        )
        uid = proxy.GetConnectionUnixUser(sender)
        user = pwd.getpwuid(uid).pw_name

        proxy = BUS.get_proxy(
            "org.freedesktop.PolicyKit1",
            "/org/freedesktop/PolicyKit1/Authority",
            "org.freedesktop.PolicyKit1.Authority",
        )
        (is_auth, _, details) = proxy.CheckAuthorization(
            ("system-bus-name", {"name": Variant.new_string(sender)}),
            action,
            {},  # no details
            1,  # allow interactive user authentication
            "",  # ignore cancellation id
        )

        if not is_auth:
            logger.warning(
                "Authorization refused for user %s(%d) on %s", user, uid, action
            )
            action_name = action.rsplit('.', 1)[1].replace('-', ' ')
            raise ErrorNotAuthorized(action_name)

        logger.debug(
            "Successful authorization for user %s(%d) on %s", user, uid, action
        )


@dbus_interface(FATBUILDR_SERVICE.interface_name)
class FatbuildrInterface(InterfaceTemplate):
    """The DBus interface of Fatbuildr."""

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def Instances(self) -> List[Structure]:
        """Returns the instances list."""
        return DbusInstance.to_structure_list(self.implementation.instances())

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def Instance(self, instance: Str) -> Structure:
        """Returns the instance user id."""
        return DbusInstance.to_structure(self.implementation.instance(instance))

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesFormats(self, instance: Str) -> List[Str]:
        """Returns the list of formats defined in pipelines of the given instance."""
        return self.implementation.pipelines_formats(instance)

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesArchitectures(self, instance: Str) -> List[Str]:
        """Returns the list of architectures defined in pipelines of the given instance."""
        return self.implementation.pipelines_architectures(instance)

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesFormatDistributions(
        self, instance: Str, format: Str
    ) -> List[Str]:
        """Returns the distributions of the given format in the pipelines of the instance."""
        return self.implementation.pipelines_format_distributions(
            instance, format
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesDistributionFormat(
        self, instance: Str, distribution: Str
    ) -> Str:
        """Returns the format of the given distribution in the pipelines of the instance."""
        return self.implementation.pipelines_distribution_format(
            instance, distribution
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesDistributionEnvironment(
        self, instance: Str, distribution: Str
    ) -> Str:
        """Returns the environment of the given distribution in the pipelines of the instance."""
        try:
            return self.implementation.pipelines_distribution_environment(
                instance, distribution
            )
        except RuntimeError:
            return 'none'

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesDistributionDerivatives(
        self, instance: Str, distribution: Str
    ) -> List[Str]:
        """Returns the derivatives of the given distribution in the pipelines of the instance."""
        return self.implementation.pipelines_distribution_derivatives(
            instance, distribution
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesDerivativeFormats(
        self, instance: Str, derivative: Str
    ) -> List[Str]:
        """Returns the formats of the given derivative in the pipelines of the instance."""
        return self.implementation.pipelines_derivative_formats(
            instance, derivative
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-task")
    def Queue(self, instance: Str) -> List[Structure]:
        """The list of tasks in queue."""
        return DbusRunnableTask.to_structure_list(
            self.implementation.queue(instance)
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-task")
    def Running(self, instance: Str) -> Structure:
        """The currently running task"""
        return DbusRunnableTask.to_structure(
            self.implementation.running(instance)
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-task")
    def Archives(self, instance: Str, limit: Int) -> List[Structure]:
        """The list of last limit tasks in archives."""
        return DbusRunnableTask.to_structure_list(
            self.implementation.archives(instance, limit)
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-registry")
    def Formats(self, instance: Str) -> List[Str]:
        """The list of available formats in an instance registries."""
        return self.implementation.formats(instance)

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-registry")
    def Distributions(self, instance: Str, fmt: Str) -> List[Str]:
        """The list of available distributions for a format in an instance
        registries."""
        return self.implementation.distributions(instance, fmt)

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-registry")
    def Derivatives(
        self, instance: Str, fmt: Str, distribution: Str
    ) -> List[Str]:
        """The list of available derivatives for a distribution in an instance
        registries."""
        return self.implementation.derivatives(instance, fmt, distribution)

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-registry")
    def Artifacts(
        self,
        instance: Str,
        fmt: Str,
        distribution: Str,
        derivative: Str,
    ) -> List[Structure]:
        """The artifacts in this derivative of this distribution registry."""
        return DbusArtifact.to_structure_list(
            self.implementation.artifacts(
                instance, fmt, distribution, derivative
            )
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.edit-registry")
    def ArtifactDelete(
        self,
        instance: Str,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        artifact: Structure,
    ) -> Str:
        """Submit artifact deletion task."""
        return self.implementation.submit(
            instance,
            'artifact deletion',
            fmt,
            distribution,
            derivative,
            DbusArtifact.from_structure(artifact).to_native(),
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-registry")
    def ArtifactBinaries(
        self,
        instance: Str,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        src_artifact: Str,
    ) -> List[Structure]:
        """Return the list of binary artifacts generated by the given source
        artifact in this derivative of this distribution registry."""
        return DbusArtifact.to_structure_list(
            self.implementation.artifact_bins(
                instance, fmt, distribution, derivative, src_artifact
            )
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-registry")
    def ArtifactSource(
        self,
        instance: Str,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        bin_artifact: Str,
    ) -> Structure:
        """Return the source artifact that generated by the given binary
        artifact in this derivative of this distribution registry."""
        src = self.implementation.artifact_src(
            instance, fmt, distribution, derivative, bin_artifact
        )
        if not src:
            raise ErrorArtifactNotFound()
        return DbusArtifact.to_structure(src)

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-registry")
    def Changelog(
        self,
        instance: Str,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        architecture: Str,
        artifact: Str,
    ) -> List[Structure]:
        """Return the list of changelog entries of the the given artifact and
        architecture in this derivative of this distribution registry."""
        return DbusChangelogEntry.to_structure_list(
            self.implementation.changelog(
                instance, fmt, distribution, derivative, architecture, artifact
            )
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.build")
    def Build(
        self,
        instance: Str,
        format: Str,
        distribution: Str,
        architectures: List[Str],
        derivative: Str,
        artifact: Str,
        user_name: Str,
        user_email: Str,
        message: Str,
        tarball: Str,
        src_tarball: Str,
        interactive: Bool,
    ) -> Str:
        """Submit a new build."""
        return self.implementation.submit(
            instance,
            'artifact build',
            format,
            distribution,
            architectures,
            derivative,
            artifact,
            user_name,
            user_email,
            message,
            tarball,
            valueornone(src_tarball),
            interactive,
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.edit-keyring")
    def KeyringCreate(self, instance: Str) -> Str:
        """Create instance keyring."""
        return self.implementation.submit(instance, 'keyring creation')

    @require_polkit_authorization("org.rackslab.Fatbuildr.edit-keyring")
    def KeyringRenew(self, instance: Str, duration: Str) -> Str:
        """Extend instance keyring expiry with new duration."""
        return self.implementation.submit(instance, 'keyring renewal', duration)

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-keyring")
    def Keyring(self, instance: Str) -> Structure:
        try:
            return DbusKeyring.to_structure(
                self.implementation.keyring(instance)
            )
        except AttributeError:
            raise ErrorNoKeyring()

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-keyring")
    def KeyringExport(self, instance: Str) -> Str:
        """Returns armored public key of instance keyring."""
        return self.implementation.keyring_export(instance)

    @require_polkit_authorization("org.rackslab.Fatbuildr.manage-image")
    def ImageCreate(self, instance: Str, format: Str, force: Bool) -> Str:
        """Submit an image creation task and returns the task id."""
        return self.implementation.submit(
            instance, 'image creation', format, force
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.manage-image")
    def ImageUpdate(self, instance: Str, format: Str) -> Str:
        """Submit an image update task and returns the task id."""
        return self.implementation.submit(instance, 'image update', format)

    @require_polkit_authorization("org.rackslab.Fatbuildr.manage-image")
    def ImageEnvironmentCreate(
        self, instance: Str, format: Str, environment: Str, architecture: Str
    ) -> Str:
        """Submit an image build environment creation task and returns the task id."""
        return self.implementation.submit(
            instance,
            'image build environment creation',
            format,
            environment,
            architecture,
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.manage-image")
    def ImageEnvironmentUpdate(
        self, instance: Str, format: Str, environment: Str, architecture: Str
    ) -> Str:
        """Submit an image build environment update task and returns the task id."""
        return self.implementation.submit(
            instance,
            'image build environment update',
            format,
            environment,
            architecture,
        )


class FatbuildrMultiplexer(object):
    """The implementation of Fatbuildr Manager."""

    def __init__(self, instances, timer):
        self._instances = instances
        self.timer = timer

    def instances(self):
        self.timer.reset()
        return self._instances

    def instance(self, instance: Str):
        self.timer.reset()
        return self._instances[instance]

    def pipelines_formats(self, instance: Str):
        self.timer.reset()
        return self._instances[instance].pipelines.formats

    def pipelines_architectures(self, instance: Str):
        self.timer.reset()
        return self._instances[instance].pipelines.architectures

    def pipelines_format_distributions(self, instance: Str, format: Str):
        self.timer.reset()
        return self._instances[instance].pipelines.format_dists(format)

    def pipelines_distribution_format(self, instance: Str, distribution: Str):
        self.timer.reset()
        return self._instances[instance].pipelines.dist_format(distribution)

    def pipelines_distribution_derivatives(
        self, instance: Str, distribution: Str
    ):
        self.timer.reset()
        return self._instances[instance].pipelines.dist_derivatives(
            distribution
        )

    def pipelines_distribution_environment(
        self, instance: Str, distribution: Str
    ):
        self.timer.reset()
        return self._instances[instance].pipelines.dist_env(distribution)

    def pipelines_derivative_formats(self, instance: Str, derivative: Str):
        self.timer.reset()
        return self._instances[instance].pipelines.derivative_formats(
            derivative
        )

    def queue(self, instance):
        """The list of builds in instance queue."""
        self.timer.reset()
        return self._instances[instance].tasks_mgr.queue.dump()

    def running(self, instance):
        """The list of builds in queue."""
        self.timer.reset()
        if not self._instances[instance].tasks_mgr.running:
            raise ErrorNoRunningTask()
        return self._instances[instance].tasks_mgr.running

    def archives(self, instance, limit):
        """The list of archived builds."""
        self.timer.reset()
        return self._instances[instance].archives_mgr.dump(limit)

    def formats(self, instance: Str):
        self.timer.reset()
        return self._instances[instance].registry_mgr.formats()

    def distributions(self, instance: Str, fmt: Str):
        self.timer.reset()
        return self._instances[instance].registry_mgr.distributions(fmt)

    def derivatives(self, instance: Str, fmt: Str, distribution: Str):
        self.timer.reset()
        return self._instances[instance].registry_mgr.derivatives(
            fmt, distribution
        )

    def artifacts(
        self, instance: Str, fmt: Str, distribution: Str, derivative: Str
    ):
        """Get all artifacts in this derivative of this distribution registry."""
        self.timer.reset()
        return self._instances[instance].registry_mgr.artifacts(
            fmt, distribution, derivative
        )

    def artifact_bins(
        self,
        instance: Str,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        src_artifact: Str,
    ):
        """Get all binary artifacts generated by the given source artifact in
        this derivative of this distribution registry."""
        self.timer.reset()
        return self._instances[instance].registry_mgr.artifact_bins(
            fmt, distribution, derivative, src_artifact
        )

    def artifact_src(
        self,
        instance: Str,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        bin_artifact: Str,
    ):
        """Get the source artifact that generated by the given binary artifact
        in this distribution registry."""
        self.timer.reset()
        return self._instances[instance].registry_mgr.artifact_src(
            fmt, distribution, derivative, bin_artifact
        )

    def changelog(
        self,
        instance: Str,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        architecture: Str,
        artifact: Str,
    ):
        """Get the changelog of the given artifact and architecture in this
        distribution registry."""
        self.timer.reset()
        return self._instances[instance].registry_mgr.changelog(
            fmt, distribution, derivative, architecture, artifact
        )

    def submit(self, instance: Str, task: Str, *args):
        """Submit a new task and returns its ID."""
        self.timer.reset()
        task_id = self._instances[instance].tasks_mgr.submit(task, *args)
        return task_id

    def keyring(self, instance: Str):
        """Returns masterkey information."""
        self.timer.reset()
        return self._instances[instance].keyring.masterkey

    def keyring_export(self, instance: Str):
        """Returns armored public key of instance keyring."""
        self.timer.reset()
        return self._instances[instance].keyring.export()


class DbusServer(object):
    def run(self, instances, timer):

        # Print the generated XML specification.
        logger.debug(
            "Dbus service interface generated:\n %s",
            XMLGenerator.prettify_xml(FatbuildrInterface.__dbus_xml__),
        )

        # Create the Fatbuildr multiplexer.
        multiplexer = FatbuildrMultiplexer(instances, timer)

        # Publish the register at /org/rackslab/Fatbuildr.
        BUS.publish_object(
            FATBUILDR_SERVICE.object_path,
            FatbuildrInterface(multiplexer),
            server_factory=AuthorizationServerObjectHandler,
        )

        # Register the service name org.rackslab.Fatbuildr.
        BUS.register_service(FATBUILDR_SERVICE.service_name)

        # Start the event loop.
        self.loop = EventLoop()
        self.loop.run()

    def quit(self):
        self.loop.quit()
