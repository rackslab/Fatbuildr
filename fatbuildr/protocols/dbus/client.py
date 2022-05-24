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
    REGISTER,
    DbusInstance,
    DbusRunnableTask,
    DbusArtifact,
    DbusChangelogEntry,
    DbusKeyring,
    ErrorNotAuthorized,
    ErrorNoRunningTask,
    ErrorNoKeyring,
    ErrorArtifactNotFound,
    valueornull,
)
from ..client import AbstractClient
from ...console.client import tty_client_console, console_client, console_reader


def check_authorization(method):
    """Decorator for DbusClient methods to catch ErrorNotAuthorized that could
    be sent by DbusServer and transform them in generic PermissionError."""

    def authorization_wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except ErrorNotAuthorized as err:
            raise PermissionError(err)

    return authorization_wrapper


class DbusClient(AbstractClient):
    def __init__(self, uri, scheme, instance):
        super().__init__(uri, scheme, instance)
        self.proxy = REGISTER.get_proxy()

    # instances and pipelines

    @check_authorization
    def instances(self):
        return DbusInstance.from_structure_list(self.proxy.Instances)

    @check_authorization
    def instance(self, id):
        return DbusInstance.from_structure(self.proxy.Instance(id))

    @check_authorization
    def pipelines_formats(self):
        return self.proxy.PipelinesFormats(self.instance)

    @check_authorization
    def pipelines_architectures(self):
        return self.proxy.PipelinesArchitectures(self.instance)

    @check_authorization
    def pipelines_format_distributions(self, format):
        return self.proxy.PipelinesFormatDistributions(self.instance, format)

    @check_authorization
    def pipelines_distribution_format(self, distribution):
        return self.proxy.PipelinesDistributionFormat(
            self.instance, distribution
        )

    @check_authorization
    def pipelines_distribution_derivatives(self, distribution):
        return self.proxy.PipelinesDistributionDerivatives(
            self.instance, distribution
        )

    @check_authorization
    def pipelines_distribution_environment(self, distribution):
        env = self.proxy.PipelinesDistributionEnvironment(
            self.instance, distribution
        )
        if env == 'none':
            return None
        return env

    @check_authorization
    def pipelines_derivative_formats(self, derivative):
        return self.proxy.PipelinesDerivativeFormats(self.instance, derivative)

    # registries

    @check_authorization
    def formats(self):
        return self.proxy.Formats(self.instance)

    @check_authorization
    def distributions(self, fmt):
        return self.proxy.Distributions(self.instance, fmt)

    @check_authorization
    def derivatives(self, fmt, distribution):
        return self.proxy.Derivatives(self.instance, fmt, distribution)

    @check_authorization
    def artifacts(self, fmt, distribution, derivative):
        return DbusArtifact.from_structure_list(
            self.proxy.Artifacts(self.instance, fmt, distribution, derivative)
        )

    @check_authorization
    def delete_artifact(self, fmt, distribution, derivative, artifact):
        return self.proxy.ArtifactDelete(
            self.instance,
            fmt,
            distribution,
            derivative,
            DbusArtifact.to_structure(artifact),
        )

    @check_authorization
    def artifact_bins(self, fmt, distribution, derivative, artifact):
        return DbusArtifact.from_structure_list(
            self.proxy.ArtifactBinaries(
                self.instance, fmt, distribution, derivative, artifact
            )
        )

    @check_authorization
    def artifact_src(self, fmt, distribution, derivative, artifact):
        try:
            return DbusArtifact.from_structure(
                self.proxy.ArtifactSource(
                    self.instance, fmt, distribution, derivative, artifact
                )
            )
        except ErrorArtifactNotFound:
            return None

    @check_authorization
    def changelog(self, fmt, distribution, derivative, architecture, artifact):
        return DbusChangelogEntry.from_structure_list(
            self.proxy.Changelog(
                self.instance,
                fmt,
                distribution,
                derivative,
                architecture,
                artifact,
            )
        )

    @check_authorization
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
        src_tarball,
        interactive,
    ):
        return self.proxy.Build(
            self.instance,
            format,
            distribution,
            architectures,
            derivative,
            artifact,
            user_name,
            user_email,
            message,
            str(tarball),
            str(valueornull(src_tarball)),
            interactive,
        )

    @check_authorization
    def queue(self):
        return DbusRunnableTask.from_structure_list(
            self.proxy.Queue(self.instance)
        )

    @check_authorization
    def running(self):
        try:
            return DbusRunnableTask.from_structure(
                self.proxy.Running(self.instance)
            )
        except ErrorNoRunningTask:
            return None

    @check_authorization
    def archives(self, limit):
        return DbusRunnableTask.from_structure_list(
            self.proxy.Archives(self.instance, limit)
        )

    def get(self, task_id):
        for _task in self.queue():
            if _task.id == task_id:
                return _task
        _running = self.running()
        if _running and _running.id == task_id:
            return _running
        for _task in self.archives(limit=0):
            if _task.id == task_id:
                return _task
        raise RuntimeError(f"Unable to find task {task_id} on server")

    def watch(self, task):
        """Dbus clients run on the same host as the server, they access the
        tasks log files directly."""
        assert hasattr(task, 'io')
        if task.state == 'running':
            console_client(task.io)
        else:
            console_reader(task.io)

    def attach(self, task):
        assert hasattr(task, 'io')
        tty_client_console(task.io)

    # keyring

    @check_authorization
    def keyring_create(self):
        return self.proxy.KeyringCreate(self.instance)

    @check_authorization
    def keyring_renew(self, duration):
        return self.proxy.KeyringRenew(self.instance, duration)

    @check_authorization
    def keyring(self):
        try:
            return DbusKeyring.from_structure(self.proxy.Keyring(self.instance))
        except ErrorNoKeyring:
            return None

    @check_authorization
    def keyring_export(self):
        return self.proxy.KeyringExport(self.instance)

    # images

    @check_authorization
    def image_create(self, format, force):
        return self.proxy.ImageCreate(self.instance, format, force)

    @check_authorization
    def image_update(self, format):
        return self.proxy.ImageUpdate(self.instance, format)

    @check_authorization
    def image_environment_create(self, format, environment, architecture):
        return self.proxy.ImageEnvironmentCreate(
            self.instance, format, environment, architecture
        )

    @check_authorization
    def image_environment_update(self, format, environment, architecture):
        return self.proxy.ImageEnvironmentUpdate(
            self.instance, format, environment, architecture
        )
