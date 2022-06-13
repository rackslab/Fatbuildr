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
from dasbus.server.publishable import Publishable
from dasbus.namespace import get_dbus_path
from dasbus.signal import Signal
from dasbus.typing import Structure, List, Str, Int, Bool, Variant, ObjPath
from dasbus.xml import XMLGenerator

from . import (
    FATBUILDR_SERVICE,
    FATBUILDR_INSTANCE,
    INSTANCES_NAMESPACE,
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


# Method attribute for the @require_polkit_authorization decorator.
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
class FatbuildrDbusServiceInterface(InterfaceTemplate):
    """The DBus interface of the Fatbuildr service."""

    def GetInstance(self, id: Str) -> ObjPath:
        """Returns the FatbuildrDbusInstance object path."""
        return self.implementation.get_instance(id)

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def Instances(self) -> List[Structure]:
        """Returns the instances list."""
        return DbusInstance.to_structure_list(self.implementation.instances())


class FatbuildrDbusService(Publishable):
    """The implementation of the FatbuildrDbusService."""

    def __init__(self, instances, timer):
        self._instances = {}  # dict of Publishable FatbuildrDbusInstances
        self.instances = instances  # list of RunningInstances
        self.timer = timer

        for instance in instances:
            obj = FatbuildrDbusInstance(instance, timer)
            object_path = get_dbus_path(
                *INSTANCES_NAMESPACE,
                instance.id,
            )
            BUS.publish_object(
                object_path,
                obj.for_publication(),
                server_factory=AuthorizationServerObjectHandler,
            )
            self._instances[instance.id] = object_path

    def for_publication(self):
        """Return a DBus representation."""
        return FatbuildrDbusServiceInterface(self)

    def get_instance(self, id):
        """Returns the Fatbuildr instance publishable object."""
        return self._instances[id]

    def instances(self):
        self.timer.reset()
        return self.instances


@dbus_interface(FATBUILDR_INSTANCE.interface_name)
class FatbuildrDbusInstanceInterface(InterfaceTemplate):
    """The DBus interface of Fatbuildr instances."""

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def Instance(self) -> Structure:
        """Returns the instance user id."""
        return DbusInstance.to_structure(self.implementation.instance())

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesFormats(self) -> List[Str]:
        """Returns the list of formats defined in pipelines of the given instance."""
        return self.implementation.pipelines_formats()

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesArchitectures(self) -> List[Str]:
        """Returns the list of architectures defined in pipelines of the given instance."""
        return self.implementation.pipelines_architectures()

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesFormatDistributions(self, format: Str) -> List[Str]:
        """Returns the distributions of the given format in the pipelines of the instance."""
        return self.implementation.pipelines_format_distributions(format)

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesDistributionFormat(self, distribution: Str) -> Str:
        """Returns the format of the given distribution in the pipelines of the instance."""
        return self.implementation.pipelines_distribution_format(distribution)

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesDistributionEnvironment(self, distribution: Str) -> Str:
        """Returns the environment of the given distribution in the pipelines of the instance."""
        try:
            return self.implementation.pipelines_distribution_environment(
                distribution
            )
        except RuntimeError:
            return 'none'

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesDistributionDerivatives(self, distribution: Str) -> List[Str]:
        """Returns the derivatives of the given distribution in the pipelines of the instance."""
        return self.implementation.pipelines_distribution_derivatives(
            distribution
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesDerivativeFormats(self, derivative: Str) -> List[Str]:
        """Returns the formats of the given derivative in the pipelines of the instance."""
        return self.implementation.pipelines_derivative_formats(derivative)

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-task")
    def Queue(self) -> List[Structure]:
        """The list of tasks in queue."""
        return DbusRunnableTask.to_structure_list(self.implementation.queue())

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-task")
    def Running(self) -> Structure:
        """The currently running task"""
        return DbusRunnableTask.to_structure(self.implementation.running())

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-task")
    def Archives(self, limit: Int) -> List[Structure]:
        """The list of last limit tasks in archives."""
        return DbusRunnableTask.to_structure_list(
            self.implementation.archives(limit)
        )

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-registry")
    def Formats(self) -> List[Str]:
        """The list of available formats in an instance registries."""
        return self.implementation.formats()

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-registry")
    def Distributions(self, fmt: Str) -> List[Str]:
        """The list of available distributions for a format in an instance
        registries."""
        return self.implementation.distributions(fmt)

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-registry")
    def Derivatives(self, fmt: Str, distribution: Str) -> List[Str]:
        """The list of available derivatives for a distribution in an instance
        registries."""
        return self.implementation.derivatives(fmt, distribution)

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-registry")
    def Artifacts(
        self,
        fmt: Str,
        distribution: Str,
        derivative: Str,
    ) -> List[Structure]:
        """The artifacts in this derivative of this distribution registry."""
        return DbusArtifact.to_structure_list(
            self.implementation.artifacts(fmt, distribution, derivative)
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.edit-registry")
    def ArtifactDelete(
        self,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        artifact: Structure,
    ) -> Str:
        """Submit artifact deletion task."""
        return self.implementation.submit(
            'artifact deletion',
            fmt,
            distribution,
            derivative,
            DbusArtifact.from_structure(artifact).to_native(),
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-registry")
    def ArtifactBinaries(
        self,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        src_artifact: Str,
    ) -> List[Structure]:
        """Return the list of binary artifacts generated by the given source
        artifact in this derivative of this distribution registry."""
        return DbusArtifact.to_structure_list(
            self.implementation.artifact_bins(
                fmt, distribution, derivative, src_artifact
            )
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-registry")
    def ArtifactSource(
        self,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        bin_artifact: Str,
    ) -> Structure:
        """Return the source artifact that generated by the given binary
        artifact in this derivative of this distribution registry."""
        src = self.implementation.artifact_src(
            fmt, distribution, derivative, bin_artifact
        )
        if not src:
            raise ErrorArtifactNotFound()
        return DbusArtifact.to_structure(src)

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-registry")
    def Changelog(
        self,
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
                fmt, distribution, derivative, architecture, artifact
            )
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.build")
    def Build(
        self,
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
    def KeyringCreate(self) -> Str:
        """Create instance keyring."""
        return self.implementation.submit('keyring creation')

    @require_polkit_authorization("org.rackslab.Fatbuildr.edit-keyring")
    def KeyringRenew(self, duration: Str) -> Str:
        """Extend instance keyring expiry with new duration."""
        return self.implementation.submit('keyring renewal', duration)

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-keyring")
    def Keyring(self) -> Structure:
        try:
            return DbusKeyring.to_structure(self.implementation.keyring())
        except AttributeError:
            raise ErrorNoKeyring()

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-keyring")
    def KeyringExport(self) -> Str:
        """Returns armored public key of instance keyring."""
        return self.implementation.keyring_export()

    @require_polkit_authorization("org.rackslab.Fatbuildr.manage-image")
    def ImageCreate(self, format: Str, force: Bool) -> Str:
        """Submit an image creation task and returns the task id."""
        return self.implementation.submit('image creation', format, force)

    @require_polkit_authorization("org.rackslab.Fatbuildr.manage-image")
    def ImageUpdate(self, format: Str) -> Str:
        """Submit an image update task and returns the task id."""
        return self.implementation.submit('image update', format)

    @require_polkit_authorization("org.rackslab.Fatbuildr.manage-image")
    def ImageEnvironmentCreate(
        self, format: Str, environment: Str, architecture: Str
    ) -> Str:
        """Submit an image build environment creation task and returns the task id."""
        return self.implementation.submit(
            'image build environment creation',
            format,
            environment,
            architecture,
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.manage-image")
    def ImageEnvironmentUpdate(
        self, format: Str, environment: Str, architecture: Str
    ) -> Str:
        """Submit an image build environment update task and returns the task id."""
        return self.implementation.submit(
            'image build environment update',
            format,
            environment,
            architecture,
        )


class FatbuildrDbusInstance(Publishable):
    """The implementation of FatbuildrDbusInstanceInterface."""

    def __init__(self, instance, timer):
        self._instance = instance  # the corresponding Fatbuildr RunningInstance
        self.timer = timer

    def for_publication(self):
        """Return a DBus representation."""
        return FatbuildrDbusInstanceInterface(self)

    def instance(self):
        self.timer.reset()
        return self._instance

    def pipelines_formats(self):
        self.timer.reset()
        return self._instance.pipelines.formats

    def pipelines_architectures(self):
        self.timer.reset()
        return self._instance.pipelines.architectures

    def pipelines_format_distributions(self, format: Str):
        self.timer.reset()
        return self._instance.pipelines.format_dists(format)

    def pipelines_distribution_format(self, distribution: Str):
        self.timer.reset()
        return self._instance.pipelines.dist_format(distribution)

    def pipelines_distribution_derivatives(self, distribution: Str):
        self.timer.reset()
        return self._instance.pipelines.dist_derivatives(distribution)

    def pipelines_distribution_environment(self, distribution: Str):
        self.timer.reset()
        return self._instance.pipelines.dist_env(distribution)

    def pipelines_derivative_formats(self, derivative: Str):
        self.timer.reset()
        return self._instance.pipelines.derivative_formats(derivative)

    def queue(self):
        """The list of builds in instance queue."""
        self.timer.reset()
        return self._instance.tasks_mgr.queue.dump()

    def running(self):
        """The list of builds in queue."""
        self.timer.reset()
        if not self._instance.tasks_mgr.running:
            raise ErrorNoRunningTask()
        return self._instance.tasks_mgr.running

    def archives(self, limit):
        """The list of archived builds."""
        self.timer.reset()
        return self._instance.archives_mgr.dump(limit)

    def formats(self):
        self.timer.reset()
        return self._instance.registry_mgr.formats()

    def distributions(self, fmt: Str):
        self.timer.reset()
        return self._instance.registry_mgr.distributions(fmt)

    def derivatives(self, fmt: Str, distribution: Str):
        self.timer.reset()
        return self._instance.registry_mgr.derivatives(fmt, distribution)

    def artifacts(self, fmt: Str, distribution: Str, derivative: Str):
        """Get all artifacts in this derivative of this distribution registry."""
        self.timer.reset()
        return self._instance.registry_mgr.artifacts(
            fmt, distribution, derivative
        )

    def artifact_bins(
        self,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        src_artifact: Str,
    ):
        """Get all binary artifacts generated by the given source artifact in
        this derivative of this distribution registry."""
        self.timer.reset()
        return self._instance.registry_mgr.artifact_bins(
            fmt, distribution, derivative, src_artifact
        )

    def artifact_src(
        self,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        bin_artifact: Str,
    ):
        """Get the source artifact that generated by the given binary artifact
        in this distribution registry."""
        self.timer.reset()
        return self._instance.registry_mgr.artifact_src(
            fmt, distribution, derivative, bin_artifact
        )

    def changelog(
        self,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        architecture: Str,
        artifact: Str,
    ):
        """Get the changelog of the given artifact and architecture in this
        distribution registry."""
        self.timer.reset()
        return self._instance.registry_mgr.changelog(
            fmt, distribution, derivative, architecture, artifact
        )

    def submit(self, task: Str, *args):
        """Submit a new task and returns its ID."""
        self.timer.reset()
        return self._instance.tasks_mgr.submit(task, *args)

    def keyring(self):
        """Returns masterkey information."""
        self.timer.reset()
        return self._instance.keyring.masterkey

    def keyring_export(self):
        """Returns armored public key of instance keyring."""
        self.timer.reset()
        return self._instance.keyring.export()


class DbusServer(object):
    def run(self, instances, timer):

        # Print the generated XML specification.
        logger.debug(
            "Fatbuildr Dbus service interface generated:\n %s",
            XMLGenerator.prettify_xml(
                FatbuildrDbusServiceInterface.__dbus_xml__
            ),
        )
        logger.debug(
            "Fatbuildr Dbus instance interface generated:\n %s",
            XMLGenerator.prettify_xml(
                FatbuildrDbusInstanceInterface.__dbus_xml__
            ),
        )

        # Create the Fatbuildr Dbus Service.
        service = FatbuildrDbusService(instances, timer)

        # Publish the Fatbuildr Dbus Service at /org/rackslab/Fatbuildr.
        BUS.publish_object(
            FATBUILDR_SERVICE.object_path,
            service.for_publication(),
            server_factory=AuthorizationServerObjectHandler,
        )

        # Register the service name org.rackslab.Fatbuildr.
        BUS.register_service(FATBUILDR_SERVICE.service_name)

        # Start the event loop.
        self.loop = EventLoop()
        self.loop.run()

    def quit(self):
        self.loop.quit()
