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

import subprocess

from . import (
    REGISTER,
    DbusInstance,
    DbusRunnableTask,
    DbusArtefact,
    DbusChangelogEntry,
    DbusKeyring,
    ErrorNoRunningTask,
    ErrorNoKeyring,
)


class DbusClient(object):
    def __init__(self, instance):
        self.instance = instance
        self.proxy = REGISTER.get_proxy()

    # instances and pipelines

    def instances(self):
        return DbusInstance.from_structure_list(self.proxy.Instances)

    def instance(self, id):
        return DbusInstance.from_structure(self.proxy.Instance(id))

    def pipelines_formats(self):
        return self.proxy.PipelinesFormats(self.instance)

    def pipelines_format_distributions(self, format):
        return self.proxy.PipelinesFormatDistributions(self.instance, format)

    def pipelines_distribution_format(self, distribution):
        return self.proxy.PipelinesDistributionFormat(
            self.instance, distribution
        )

    def pipelines_distribution_derivatives(self, distribution):
        return self.proxy.PipelinesDistributionDerivatives(
            self.instance, distribution
        )

    def pipelines_distribution_environment(self, distribution):
        env = self.proxy.PipelinesDistributionEnvironment(
            self.instance, distribution
        )
        if env == 'none':
            return None
        return env

    def pipelines_derivative_formats(self, derivative):
        return self.proxy.PipelinesDerivativeFormats(self.instance, derivative)

    # registries

    def formats(self):
        return self.proxy.Formats(self.instance)

    def distributions(self, fmt):
        return self.proxy.Distributions(self.instance, fmt)

    def derivatives(self, fmt, distribution):
        return self.proxy.Derivatives(self.instance, fmt, distribution)

    def artefacts(self, fmt, distribution, derivative):
        return DbusArtefact.from_structure_list(
            self.proxy.Artefacts(self.instance, fmt, distribution, derivative)
        )

    def delete_artefact(self, fmt, distribution, derivative, artefact):
        return self.proxy.ArtefactDelete(
            self.instance,
            fmt,
            distribution,
            derivative,
            DbusArtefact.to_structure(artefact),
        )

    def artefact_bins(self, fmt, distribution, derivative, artefact):
        return DbusArtefact.from_structure_list(
            self.proxy.ArtefactBinaries(
                self.instance, fmt, distribution, derivative, artefact
            )
        )

    def artefact_src(self, fmt, distribution, derivative, artefact):
        return DbusArtefact.from_structure(
            self.proxy.ArtefactSource(
                self.instance, fmt, distribution, derivative, artefact
            )
        )

    def changelog(self, fmt, distribution, derivative, architecture, artefact):
        return DbusChangelogEntry.from_structure_list(
            self.proxy.Changelog(
                self.instance,
                fmt,
                distribution,
                derivative,
                architecture,
                artefact,
            )
        )

    def submit(
        self,
        format,
        distribution,
        derivative,
        artefact,
        user_name,
        user_email,
        message,
        tarball,
    ):
        return self.proxy.Submit(
            self.instance,
            format,
            distribution,
            derivative,
            artefact,
            user_name,
            user_email,
            message,
            str(tarball),
        )

    def queue(self):
        return DbusRunnableTask.from_structure_list(
            self.proxy.Queue(self.instance)
        )

    def running(self):
        try:
            return DbusRunnableTask.from_structure(
                self.proxy.Running(self.instance)
            )
        except ErrorNoRunningTask:
            return None

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
        raise RuntimeError(f"Unable to find task {build_id} on server")

    def watch(self, task):
        """Dbus clients run on the same host as the server, they access the
        tasks log files directly."""
        assert hasattr(task, 'logfile')
        proc = None
        if task.state == 'running':
            # Follow the log file. It has been choosen to exec `tail -f`
            # because python lacks well maintained and common inotify library.
            # This tail command is in coreutils and it is installed basically
            # everywhere.
            cmd = ['tail', '--follow', task.logfile]
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            fh = proc.stdout
        else:
            # dump full task log
            fh = open(task.logfile, 'rb')

        while True:
            b_line = fh.readline()
            if not b_line:
                break
            line = b_line.decode()
            # terminate `tail` if launched and log end is reached
            if (
                line.startswith("Task failed")
                or line.startswith("Task succeeded")
            ) and proc:
                proc.terminate()
            yield line

        fh.close()

    # keyring

    def keyring_create(self):
        return self.proxy.KeyringCreate(self.instance)

    def keyring_renew(self, duration):
        return self.proxy.KeyringRenew(self.instance, duration)

    def keyring(self):
        try:
            return DbusKeyring.from_structure(self.proxy.Keyring(self.instance))
        except ErrorNoKeyring:
            return None

    def keyring_export(self):
        return self.proxy.KeyringExport(self.instance)

    # images

    def image_create(self, format, force):
        return self.proxy.ImageCreate(self.instance, format, force)

    def image_update(self, format):
        return self.proxy.ImageUpdate(self.instance, format)

    def image_environment_create(self, format, environment):
        return self.proxy.ImageEnvironmentCreate(
            self.instance, format, environment
        )

    def image_environment_update(self, format, environment):
        return self.proxy.ImageEnvironmentUpdate(
            self.instance, format, environment
        )
