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
    DbusSubmittedBuild,
    DbusRunningBuild,
    DbusArchivedBuild,
    DbusArtefact,
    DbusChangelogEntry,
    ErrorNoRunningBuild,
)


class DbusClient(object):
    def __init__(self):
        self.proxy = REGISTER.get_proxy()

    # instances

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

    def registry_instances(self):
        return self.proxy.RegistryInstances

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

    def submit(self, instance, request):
        return self.proxy.Submit(instance, request.place)

    def queue(self, instance):
        return DbusSubmittedBuild.from_structure_list(
            self.proxy.Queue(instance)
        )

    def running(self, instance):
        try:
            return DbusRunningBuild.from_structure(self.proxy.Running(instance))
        except ErrorNoRunningBuild:
            return None

    def archives(self, instance):
        return DbusArchivedBuild.from_structure_list(
            self.proxy.Archives(instance)
        )

    def get(self, instance, build_id):
        for _build in self.queue(instance):
            if _build.id == build_id:
                return _build
        _running = self.running(instance)
        if _running and _running.id == build_id:
            return _running
        for _build in self.archives(instance):
            if _build.id == build_id:
                return _build
        raise RuntimeError("Unable to find build %s on server" % (build_id))

    def watch(self, instance, build):
        """Dbus clients run on the same host as the server, they access the
        builds log files directly."""
        assert hasattr(build, 'logfile')
        proc = None
        if build.state == 'running':
            # Follow the log file. It has been choosen to exec `tail -f`
            # because python lacks well maintained and common inotify library.
            # This tail command is in coreutils and it is installed basically
            # everywhere.
            cmd = ['tail', '--follow', build.logfile]
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            fh = proc.stdout
        else:
            # dump full build log
            fh = open(build.logfile, 'rb')

        while True:
            b_line = fh.readline()
            if not b_line:
                break
            line = b_line.decode()
            # terminate `tail` if launched and log end is reached
            if (
                line.startswith("Build failed")
                or line.startswith("Build succeeded")
            ) and proc:
                proc.terminate()
            yield line

        fh.close()

    def keyring_export(self, instance):
        return self.proxy.KeyringExport(instance)
