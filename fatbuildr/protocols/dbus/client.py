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
)


class DbusClient(object):
    def __init__(self):
        self.proxy = REGISTER.get_proxy()

    # instances

    def instances(self):
        return DbusInstance.from_structure_list(self.proxy.Instances)

    def instance(self, id):
        return DbusInstance.from_structure(self.proxy.Instance(id))

    def pipelines_formats(self, instance):
        return self.proxy.PipelinesFormats(instance)

    def pipelines_format_distributions(self, instance, format):
        return self.proxy.PipelinesFormatDistributions(instance, format)

    def pipelines_distribution_format(self, instance, distribution):
        return self.proxy.PipelinesDistributionFormat(instance, distribution)

    def pipelines_distribution_derivatives(self, instance, distribution):
        return self.proxy.PipelinesDistributionDerivatives(
            instance, distribution
        )

    def pipelines_distribution_environment(self, instance, distribution):
        env = self.proxy.PipelinesDistributionEnvironment(
            instance, distribution
        )
        if env == 'none':
            return None
        return env

    def pipelines_derivative_formats(self, instance, derivative):
        return self.proxy.PipelinesDerivativeFormats(instance, derivative)

    # registries

    def formats(self, instance):
        return self.proxy.Formats(instance)

    def distributions(self, instance, fmt):
        return self.proxy.Distributions(instance, fmt)

    def derivatives(self, instance, fmt, distribution):
        return self.proxy.Derivatives(instance, fmt, distribution)

    def artefacts(self, instance, fmt, distribution, derivative):
        return DbusArtefact.from_structure_list(
            self.proxy.Artefacts(instance, fmt, distribution, derivative)
        )

    def delete_artefact(
        self, instance, fmt, distribution, derivative, artefact
    ):
        return self.proxy.ArtefactDelete(
            instance,
            fmt,
            distribution,
            derivative,
            DbusArtefact.to_structure(artefact),
        )

    def artefact_bins(self, instance, fmt, distribution, derivative, artefact):
        return DbusArtefact.from_structure_list(
            self.proxy.ArtefactBinaries(
                instance, fmt, distribution, derivative, artefact
            )
        )

    def artefact_src(self, instance, fmt, distribution, derivative, artefact):
        return DbusArtefact.from_structure(
            self.proxy.ArtefactSource(
                instance, fmt, distribution, derivative, artefact
            )
        )

    def changelog(
        self, instance, fmt, distribution, derivative, architecture, artefact
    ):
        return DbusChangelogEntry.from_structure_list(
            self.proxy.Changelog(
                instance, fmt, distribution, derivative, architecture, artefact
            )
        )

    def submit(
        self,
        instance,
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
            instance,
            format,
            distribution,
            derivative,
            artefact,
            user_name,
            user_email,
            message,
            str(tarball),
        )

    def queue(self, instance):
        return DbusRunnableTask.from_structure_list(self.proxy.Queue(instance))

    def running(self, instance):
        try:
            return DbusRunnableTask.from_structure(self.proxy.Running(instance))
        except ErrorNoRunningTask:
            return None

    def archives(self, instance):
        return DbusRunnableTask.from_structure_list(
            self.proxy.Archives(instance)
        )

    def get(self, instance, task_id):
        for _task in self.queue(instance):
            if _task.id == task_id:
                return _task
        _running = self.running(instance)
        if _running and _running.id == task_id:
            return _running
        for _task in self.archives(instance):
            if _task.id == task_id:
                return _task
        raise RuntimeError("Unable to find task %s on server" % (build_id))

    def watch(self, instance, task):
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

    def keyring_create(self, instance):
        return self.proxy.KeyringCreate(instance)

    def keyring(self, instance):
        return DbusKeyring.from_structure(self.proxy.Keyring(instance))

    def keyring_export(self, instance):
        return self.proxy.KeyringExport(instance)

    # images

    def image_create(self, instance, format, force):
        return self.proxy.ImageCreate(instance, format, force)

    def image_update(self, instance, format):
        return self.proxy.ImageUpdate(instance, format)
