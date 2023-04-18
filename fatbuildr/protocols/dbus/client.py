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

from . import (
    FATBUILDR_SERVICE,
    DBusInstance,
    DBusSourceArchive,
    DBusRunnableTask,
    DBusArtifact,
    DBusChangelogEntry,
    DBusKeyring,
    FatbuildrDBusError,
    FatbuildrDBusErrorNotAuthorized,
    FatbuildrDBusErrorUnknownInstance,
    FatbuildrDBusErrorNoRunningTask,
    FatbuildrDBusErrorNoKeyring,
    FatbuildrDBusErrorRegistry,
)
from ..client import AbstractClient
from ...console.client import (
    tty_client_console,
    console_unix_client,
    console_reader,
)

from ...errors import (
    FatbuildrServerPermissionError,
    FatbuildrServerRegistryError,
    FatbuildrServerInstanceError,
    FatbuildrServerError,
)


def check_dbus_errors(method):
    """Decorator for DBusClient methods to catch various FatbuildrDBusError that
    could be sent by DBusServer and translate them into generic Fatbuildr server
    errors.
    """

    def error_handler_wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except FatbuildrDBusErrorNotAuthorized as err:
            raise FatbuildrServerPermissionError(err)
        except FatbuildrDBusErrorRegistry as err:
            raise FatbuildrServerRegistryError(err)
        except FatbuildrDBusError as err:
            raise FatbuildrServerError(err)

    return error_handler_wrapper


class DBusClient(AbstractClient):
    @check_dbus_errors
    def __init__(self, uri, scheme, instance):
        super().__init__(uri, scheme)
        self.service_proxy = FATBUILDR_SERVICE.get_proxy()
        try:
            obj_path = self.service_proxy.GetInstance(instance)
        except FatbuildrDBusErrorUnknownInstance:
            raise FatbuildrServerInstanceError(
                f"Unknown instance {instance} at {uri}"
            )
        self.proxy = FATBUILDR_SERVICE.get_proxy(obj_path)

    # instances and pipelines

    @check_dbus_errors
    def instances(self):
        return DBusInstance.from_structure_list(self.service_proxy.Instances)

    @check_dbus_errors
    def instance(self, id):
        return DBusInstance.from_structure(self.proxy.Instance)

    @check_dbus_errors
    def pipelines_formats(self):
        return self.proxy.PipelinesFormats

    @check_dbus_errors
    def pipelines_architectures(self):
        return self.proxy.PipelinesArchitectures

    @check_dbus_errors
    def pipelines_format_distributions(self, format):
        return self.proxy.PipelinesFormatDistributions(format)

    @check_dbus_errors
    def pipelines_distribution_format(self, distribution):
        return self.proxy.PipelinesDistributionFormat(distribution)

    @check_dbus_errors
    def pipelines_distribution_derivatives(self, distribution):
        return self.proxy.PipelinesDistributionDerivatives(distribution)

    @check_dbus_errors
    def pipelines_distribution_environment(self, distribution):
        env = self.proxy.PipelinesDistributionEnvironment(distribution)
        if env == 'none':
            return None
        return env

    @check_dbus_errors
    def pipelines_derivative_formats(self, derivative):
        return self.proxy.PipelinesDerivativeFormats(derivative)

    # registries

    @check_dbus_errors
    def formats(self):
        return self.proxy.Formats

    @check_dbus_errors
    def distributions(self, fmt):
        return self.proxy.Distributions(fmt)

    @check_dbus_errors
    def derivatives(self, fmt, distribution):
        return self.proxy.Derivatives(fmt, distribution)

    @check_dbus_errors
    def artifacts(self, fmt, distribution, derivative):
        return DBusArtifact.from_structure_list(
            self.proxy.Artifacts(fmt, distribution, derivative)
        )

    @check_dbus_errors
    def delete_artifact(self, fmt, distribution, derivative, artifact):
        return self.proxy.ArtifactDelete(
            fmt,
            distribution,
            derivative,
            DBusArtifact.to_structure(artifact),
        )

    @check_dbus_errors
    def artifact_bins(self, fmt, distribution, derivative, artifact):
        return DBusArtifact.from_structure_list(
            self.proxy.ArtifactBinaries(fmt, distribution, derivative, artifact)
        )

    @check_dbus_errors
    def artifact_src(self, fmt, distribution, derivative, artifact):
        return DBusArtifact.from_structure(
            self.proxy.ArtifactSource(fmt, distribution, derivative, artifact)
        )

    @check_dbus_errors
    def changelog(self, fmt, distribution, derivative, architecture, artifact):
        return DBusChangelogEntry.from_structure_list(
            self.proxy.Changelog(
                fmt,
                distribution,
                derivative,
                architecture,
                artifact,
            )
        )

    @check_dbus_errors
    def build(
        self,
        format,
        distribution,
        architectures,
        derivative,
        artifact,
        user_name,
        user_email,
        message,
        tarball,
        sources,
        interactive,
    ):
        return self.proxy.Build(
            format,
            distribution,
            architectures,
            derivative,
            artifact,
            user_name,
            user_email,
            message,
            str(tarball),
            DBusSourceArchive.to_structure_list(sources),
            interactive,
        )

    @check_dbus_errors
    def build_as(
        self,
        user,
        format,
        distribution,
        architectures,
        derivative,
        artifact,
        user_name,
        user_email,
        message,
        tarball,
        sources,
        interactive,
    ):
        return self.proxy.BuildAs(
            user,
            format,
            distribution,
            architectures,
            derivative,
            artifact,
            user_name,
            user_email,
            message,
            str(tarball),
            DBusSourceArchive.to_structure_list(sources),
            interactive,
        )

    @check_dbus_errors
    def queue(self):
        return DBusRunnableTask.from_structure_list(self.proxy.Queue)

    @check_dbus_errors
    def running(self):
        try:
            return DBusRunnableTask.from_structure(self.proxy.Running)
        except FatbuildrDBusErrorNoRunningTask:
            return None

    @check_dbus_errors
    def history(self, limit):
        return DBusRunnableTask.from_structure_list(self.proxy.History(limit))

    def get(self, task_id):
        for _task in self.queue():
            if _task.id == task_id:
                return _task
        _running = self.running()
        if _running and _running.id == task_id:
            return _running
        for _task in self.history(limit=0):
            if _task.id == task_id:
                return _task
        raise FatbuildrServerError(f"Unable to find task {task_id} on server")

    def watch(self, task, binary=False):
        """Returns a generator of the given task ConsoleMessages output."""
        assert hasattr(task, 'io')
        if task.state == 'running':
            return console_unix_client(task.io, binary)
        else:
            return console_reader(task.io, binary)

    def attach(self, task):
        """Setup user terminal to follow output of task running on server
        side."""
        assert hasattr(task, 'io')
        tty_client_console(task.io)

    # keyring

    @check_dbus_errors
    def keyring_create(self):
        return self.proxy.KeyringCreate()

    @check_dbus_errors
    def keyring_renew(self, duration):
        return self.proxy.KeyringRenew(duration)

    @check_dbus_errors
    def keyring(self):
        try:
            return DBusKeyring.from_structure(self.proxy.Keyring)
        except FatbuildrDBusErrorNoKeyring:
            return None

    @check_dbus_errors
    def keyring_export(self):
        return self.proxy.KeyringExport

    # images

    @check_dbus_errors
    def image_create(self, format, force):
        return self.proxy.ImageCreate(format, force)

    @check_dbus_errors
    def image_update(self, format):
        return self.proxy.ImageUpdate(format)

    @check_dbus_errors
    def image_shell(self, format, term):
        return self.proxy.ImageShell(format, term)

    @check_dbus_errors
    def image_environment_create(self, format, environment, architecture):
        return self.proxy.ImageEnvironmentCreate(
            format, environment, architecture
        )

    @check_dbus_errors
    def image_environment_update(self, format, environment, architecture):
        return self.proxy.ImageEnvironmentUpdate(
            format, environment, architecture
        )

    @check_dbus_errors
    def image_environment_shell(self, format, environment, architecture, term):
        return self.proxy.ImageEnvironmentShell(
            format, environment, architecture, term
        )

    # token
    @check_dbus_errors
    def token_generate(self):
        return self.proxy.TokenGenerate()
