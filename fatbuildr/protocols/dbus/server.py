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
    DBusInstance,
    DBusSourceArchive,
    DBusRunnableTask,
    DBusArtifact,
    DBusChangelogEntry,
    DBusKeyring,
    FatbuildrDBusErrorNotAuthorized,
    FatbuildrDBusErrorUnknownInstance,
    FatbuildrDBusErrorNoRunningTask,
    FatbuildrDBusErrorNoKeyring,
    FatbuildrDBusErrorArtifactNotFound,
    FatbuildrDBusErrorPipeline,
    valueornone,
)
from ...errors import FatbuildrPipelineError
from ...log import logr


logger = logr(__name__)


# Method attribute for the @require_polkit_authorization decorator.
REQUIRE_POLKIT_AUTHORIZATION_ATTRIBUTE = (
    "__dbus_handler_require_polkit_authorization__"
)


def dbus_user(sender):
    """Returns a tuple container the UID and the name of the user initiating the
    provided DBus sender connection name."""
    proxy = BUS.get_proxy("org.freedesktop.DBus", "/org/freedesktop/DBus")
    uid = proxy.GetConnectionUnixUser(sender)
    return (uid, pwd.getpwuid(uid).pw_name)


def require_polkit_authorization(action):
    """Decorator for InterfaceTemplate methods to check for polkit authorization
    on the given action prior to running the method. The decorator actually
    defines an attribute on the method, this attribute is consumed by
    TimeredAuthorizationServerObjectHandler to actually ask polkit about the
    authorization on the action."""

    def wrap(method):
        setattr(method, REQUIRE_POLKIT_AUTHORIZATION_ATTRIBUTE, action)
        return method

    return wrap


class TimeredAuthorizationServerObjectHandler(ServerObjectHandler):
    """Child class of dasbus ServerObjectHandler just to override _handle_call()
    method."""

    def _handle_call(
        self, interface_name, method_name, *parameters, **additional_args
    ):
        """This method resets fatbuildrd timer thread and checks if the polkit
        authorization attribute has been defined on the method by
        @require_polkit_authorization decorator. In this case, it checks sender
        authorization on the associated action."""
        handler = self._find_handler(interface_name, method_name)

        # Reset the timer thread activity counter holded by puslished object on
        # every DBus calls.
        self._object.implementation.timer.reset()

        action = getattr(handler, REQUIRE_POLKIT_AUTHORIZATION_ATTRIBUTE, None)
        if action:
            TimeredAuthorizationServerObjectHandler.check_auth(
                additional_args['call_info']['sender'], action
            )

        return super()._handle_call(
            interface_name, method_name, *parameters, **additional_args
        )

    @staticmethod
    def check_auth(sender, action):
        """This method asks polkit for given sender authorization on the given
        action. It raises FatbuildrDBusErrorNotAuthorized exception if the
        authorization fails."""
        (uid, user) = dbus_user(sender)

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
            raise FatbuildrDBusErrorNotAuthorized(
                f"action {action_name} not authorized to user {user}({uid})"
            )

        logger.debug(
            "Successful authorization for user %s(%d) on %s", user, uid, action
        )


@dbus_interface(FATBUILDR_SERVICE.interface_name)
class FatbuildrDBusServiceInterface(InterfaceTemplate):
    """The DBus interface of the Fatbuildr service."""

    def GetInstance(self, id: Str) -> ObjPath:
        """Returns the FatbuildrDBusInstance object path."""
        try:
            return self.implementation.get_instance(id)
        except KeyError:
            raise FatbuildrDBusErrorUnknownInstance()

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def Instances(self) -> List[Structure]:
        """Returns the instances list."""
        return DBusInstance.to_structure_list(self.implementation.instances())


class FatbuildrDBusService(Publishable):
    """The implementation of the FatbuildrDBusService."""

    def __init__(self, instances, timer):
        self._dbus_instances = {}  # dict of Publishable FatbuildrDBusInstances
        self._running_instances = instances  # list of RunningInstances
        self.timer = timer

        for instance in instances:
            obj = FatbuildrDBusInstance(instance, timer)
            object_path = get_dbus_path(
                *INSTANCES_NAMESPACE,
                instance.id,
            )
            BUS.publish_object(
                object_path,
                obj.for_publication(),
                server_factory=TimeredAuthorizationServerObjectHandler,
            )
            self._dbus_instances[instance.id] = object_path

    def for_publication(self):
        """Return a DBus representation."""
        return FatbuildrDBusServiceInterface(self)

    def get_instance(self, id):
        """Returns the Fatbuildr instance publishable object."""
        return self._dbus_instances[id]

    def instances(self):
        return self._running_instances


@dbus_interface(FATBUILDR_INSTANCE.interface_name)
class FatbuildrDBusInstanceInterface(InterfaceTemplate):
    """The DBus interface of Fatbuildr instances."""

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def Instance(self) -> Structure:
        """Returns the instance user id."""
        return DBusInstance.to_structure(self.implementation.instance())

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
        try:
            return self.implementation.pipelines_distribution_format(
                distribution
            )
        except FatbuildrPipelineError as err:
            raise FatbuildrDBusErrorPipeline(err)

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesDistributionEnvironment(self, distribution: Str) -> Str:
        """Returns the environment of the given distribution in the pipelines of the instance."""
        try:
            return self.implementation.pipelines_distribution_environment(
                distribution
            )
        except FatbuildrPipelineError:
            return 'none'

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesDistributionDerivatives(self, distribution: Str) -> List[Str]:
        """Returns the derivatives of the given distribution in the pipelines of the instance."""
        try:
            return self.implementation.pipelines_distribution_derivatives(
                distribution
            )
        except FatbuildrPipelineError as err:
            raise FatbuildrDBusErrorPipeline(err)

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-pipeline")
    def PipelinesDerivativeFormats(self, derivative: Str) -> List[Str]:
        """Returns the formats of the given derivative in the pipelines of the instance."""
        return self.implementation.pipelines_derivative_formats(derivative)

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-task")
    def Queue(self) -> List[Structure]:
        """The list of tasks in queue."""
        return DBusRunnableTask.to_structure_list(self.implementation.queue())

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-task")
    def Running(self) -> Structure:
        """The currently running task. FatbuildrDBusErrorNoRunningTask is raised
        if no task is currently running."""
        running = self.implementation.running()
        if running is None:
            raise FatbuildrDBusErrorNoRunningTask()
        return DBusRunnableTask.to_structure(running)

    @require_polkit_authorization("org.rackslab.Fatbuildr.view-task")
    def Archives(self, limit: Int) -> List[Structure]:
        """The list of last limit tasks in archives."""
        return DBusRunnableTask.to_structure_list(
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
        return DBusArtifact.to_structure_list(
            self.implementation.artifacts(fmt, distribution, derivative)
        )

    @accepts_additional_arguments
    @require_polkit_authorization("org.rackslab.Fatbuildr.edit-registry")
    def ArtifactDelete(
        self,
        fmt: Str,
        distribution: Str,
        derivative: Str,
        artifact: Structure,
        *,
        call_info,
    ) -> Str:
        """Submit artifact deletion task."""
        return self.implementation.submit(
            'artifact deletion',
            dbus_user(call_info['sender'])[1],
            fmt,
            distribution,
            derivative,
            DBusArtifact.from_structure(artifact).to_native(),
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
        return DBusArtifact.to_structure_list(
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
            raise FatbuildrDBusErrorArtifactNotFound()
        return DBusArtifact.to_structure(src)

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
        return DBusChangelogEntry.to_structure_list(
            self.implementation.changelog(
                fmt, distribution, derivative, architecture, artifact
            )
        )

    @accepts_additional_arguments
    @require_polkit_authorization("org.rackslab.Fatbuildr.build")
    def Build(
        self,
        format: Str,
        distribution: Str,
        architectures: List[Str],
        derivative: Str,
        artifact: Str,
        author: Str,
        email: Str,
        message: Str,
        tarball: Str,
        sources: List[Structure],
        interactive: Bool,
        *,
        call_info,
    ) -> Str:
        """Submit a new build."""
        return self.implementation.submit(
            'artifact build',
            dbus_user(call_info['sender'])[1],
            format,
            distribution,
            architectures,
            derivative,
            artifact,
            author,
            email,
            message,
            tarball,
            [
                source.to_native()
                for source in DBusSourceArchive.from_structure_list(sources)
            ],
            interactive,
        )

    @require_polkit_authorization("org.rackslab.Fatbuildr.build-as")
    def BuildAs(
        self,
        user: Str,
        format: Str,
        distribution: Str,
        architectures: List[Str],
        derivative: Str,
        artifact: Str,
        author: Str,
        email: Str,
        message: Str,
        tarball: Str,
        sources: List[Structure],
        interactive: Bool,
    ) -> Str:
        """Submit a new build."""
        return self.implementation.submit(
            'artifact build',
            user,
            format,
            distribution,
            architectures,
            derivative,
            artifact,
            author,
            email,
            message,
            tarball,
            [
                source.to_native()
                for source in DBusSourceArchive.from_structure_list(sources)
            ],
            interactive,
        )

    @accepts_additional_arguments
    @require_polkit_authorization("org.rackslab.Fatbuildr.edit-keyring")
    def KeyringCreate(self, *, call_info) -> Str:
        """Create instance keyring."""
        return self.implementation.submit(
            'keyring creation', dbus_user(call_info['sender'])[1]
        )

    @accepts_additional_arguments
    @require_polkit_authorization("org.rackslab.Fatbuildr.edit-keyring")
    def KeyringRenew(self, duration: Str, *, call_info) -> Str:
        """Extend instance keyring expiry with new duration."""
        return self.implementation.submit(
            'keyring renewal', dbus_user(call_info['sender'])[1], duration
        )

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-keyring")
    def Keyring(self) -> Structure:
        try:
            return DBusKeyring.to_structure(self.implementation.keyring())
        except AttributeError:
            raise FatbuildrDBusErrorNoKeyring()

    @property
    @require_polkit_authorization("org.rackslab.Fatbuildr.view-keyring")
    def KeyringExport(self) -> Str:
        """Returns armored public key of instance keyring."""
        return self.implementation.keyring_export()

    @accepts_additional_arguments
    @require_polkit_authorization("org.rackslab.Fatbuildr.manage-image")
    def ImageCreate(self, format: Str, force: Bool, *, call_info) -> Str:
        """Submit an image creation task and returns the task id."""
        return self.implementation.submit(
            'image creation', dbus_user(call_info['sender'])[1], format, force
        )

    @accepts_additional_arguments
    @require_polkit_authorization("org.rackslab.Fatbuildr.manage-image")
    def ImageUpdate(self, format: Str, *, call_info) -> Str:
        """Submit an image update task and returns the task id."""
        return self.implementation.submit(
            'image update', dbus_user(call_info['sender'])[1], format
        )

    @accepts_additional_arguments
    @require_polkit_authorization("org.rackslab.Fatbuildr.manage-image")
    def ImageShell(self, format: Str, term: Str, *, call_info) -> Str:
        """Submit an image shell task and returns the task id."""
        return self.implementation.submit(
            'image shell', dbus_user(call_info['sender'])[1], format, term
        )

    @accepts_additional_arguments
    @require_polkit_authorization("org.rackslab.Fatbuildr.manage-image")
    def ImageEnvironmentCreate(
        self, format: Str, environment: Str, architecture: Str, *, call_info
    ) -> Str:
        """Submit an image build environment creation task and returns the task id."""
        return self.implementation.submit(
            'image build environment creation',
            dbus_user(call_info['sender'])[1],
            format,
            environment,
            architecture,
        )

    @accepts_additional_arguments
    @require_polkit_authorization("org.rackslab.Fatbuildr.manage-image")
    def ImageEnvironmentUpdate(
        self, format: Str, environment: Str, architecture: Str, *, call_info
    ) -> Str:
        """Submit an image build environment update task and returns the task id."""
        return self.implementation.submit(
            'image build environment update',
            dbus_user(call_info['sender'])[1],
            format,
            environment,
            architecture,
        )

    @accepts_additional_arguments
    @require_polkit_authorization("org.rackslab.Fatbuildr.manage-image")
    def ImageEnvironmentShell(
        self,
        format: Str,
        environment: Str,
        architecture: Str,
        term: Str,
        *,
        call_info,
    ) -> Str:
        """Submit an image build environment shell task and returns the task id."""
        return self.implementation.submit(
            'image build environment shell',
            dbus_user(call_info['sender'])[1],
            format,
            environment,
            architecture,
            term,
        )

    @accepts_additional_arguments
    @require_polkit_authorization("org.rackslab.Fatbuildr.manage-token")
    def TokenGenerate(self, *, call_info) -> Str:
        """Returns a generated token for REST API."""
        return self.implementation.generate_token(
            dbus_user(call_info['sender'])[1]
        )


class FatbuildrDBusInstance(Publishable):
    """The implementation of FatbuildrDBusInstanceInterface."""

    def __init__(self, instance, timer):
        self._instance = instance  # the corresponding Fatbuildr RunningInstance
        self.timer = timer

    def for_publication(self):
        """Return a DBus representation."""
        return FatbuildrDBusInstanceInterface(self)

    def instance(self):
        return self._instance

    def pipelines_formats(self):
        return self._instance.pipelines.formats

    def pipelines_architectures(self):
        return self._instance.pipelines.architectures

    def pipelines_format_distributions(self, format: Str):
        return self._instance.pipelines.format_dists(format)

    def pipelines_distribution_format(self, distribution: Str):
        return self._instance.pipelines.dist_format(distribution)

    def pipelines_distribution_derivatives(self, distribution: Str):
        return self._instance.pipelines.dist_derivatives(distribution)

    def pipelines_distribution_environment(self, distribution: Str):
        return self._instance.pipelines.dist_env(distribution)

    def pipelines_derivative_formats(self, derivative: Str):
        return self._instance.pipelines.derivative_formats(derivative)

    def queue(self):
        """The list of tasks in instance queue."""
        return self._instance.tasks_mgr.queue.dump()

    def running(self):
        """The currently running task."""
        return self._instance.tasks_mgr.running

    def archives(self, limit):
        """The list of archived builds."""
        return self._instance.archives_mgr.dump(limit)

    def formats(self):
        return self._instance.registry_mgr.formats()

    def distributions(self, fmt: Str):
        return self._instance.registry_mgr.distributions(fmt)

    def derivatives(self, fmt: Str, distribution: Str):
        return self._instance.registry_mgr.derivatives(fmt, distribution)

    def artifacts(self, fmt: Str, distribution: Str, derivative: Str):
        """Get all artifacts in this derivative of this distribution registry."""
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
        return self._instance.registry_mgr.changelog(
            fmt, distribution, derivative, architecture, artifact
        )

    def submit(self, task: Str, user: Str, *args):
        """Submit a new task and returns its ID."""
        return self._instance.tasks_mgr.submit(task, user, *args)

    def keyring(self):
        """Returns masterkey information."""
        return self._instance.keyring.masterkey

    def keyring_export(self):
        """Returns armored public key of instance keyring."""
        return self._instance.keyring.export()

    def generate_token(self, user: Str):
        """Returns a generated token for HTTP REST API usage."""
        return self._instance.tokens_mgr.generate(user)


class DBusServer(object):
    def run(self, instances, timer):

        # Print the generated XML specification.
        logger.debug(
            "Fatbuildr DBus service interface generated:\n %s",
            XMLGenerator.prettify_xml(
                FatbuildrDBusServiceInterface.__dbus_xml__
            ),
        )
        logger.debug(
            "Fatbuildr DBus instance interface generated:\n %s",
            XMLGenerator.prettify_xml(
                FatbuildrDBusInstanceInterface.__dbus_xml__
            ),
        )

        # Create the Fatbuildr DBus Service.
        service = FatbuildrDBusService(instances, timer)

        # Publish the Fatbuildr DBus Service at /org/rackslab/Fatbuildr.
        BUS.publish_object(
            FATBUILDR_SERVICE.object_path,
            service.for_publication(),
            server_factory=TimeredAuthorizationServerObjectHandler,
        )

        # Register the service name org.rackslab.Fatbuildr.
        BUS.register_service(FATBUILDR_SERVICE.service_name)

        # Start the event loop.
        self.loop = EventLoop()
        self.loop.run()

    def quit(self):
        # Disconnect from the bus so the system manager takes back DBus service
        # handling and reactivate the service with the next coming client.
        logger.debug("Disconnecting service from DBus")
        BUS.disconnect()
        logger.debug("Exiting server event loop")
        self.loop.quit()
