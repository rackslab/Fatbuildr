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

from . import RunnableTask

from ..protocols.exports import ExportableTaskField
from ..registry.formats import RegistryArtifact
from ..log import logr

logger = logr(__name__)


class RegistryArtifactDeletionTask(RunnableTask):

    TASK_NAME = 'artifact deletion'

    EXFIELDS = {
        ExportableTaskField('format'),
        ExportableTaskField('distribution'),
        ExportableTaskField('derivative'),
        ExportableTaskField('artifact', RegistryArtifact),
    }

    def __init__(
        self,
        task_id,
        user,
        place,
        instance,
        format,
        distribution,
        derivative,
        artifact,
    ):
        super().__init__(task_id, user, place, instance)
        self.format = format
        self.distribution = distribution
        self.derivative = derivative
        self.artifact = artifact

    def run(self):
        logger.info(
            "Running artifact deletion task %s %s>%s>%s>%s",
            self.id,
            self.format,
            self.distribution,
            self.derivative,
            self.artifact.name,
        )
        self.instance.registry_mgr.delete_artifact(
            self.format,
            self.distribution,
            self.derivative,
            self.artifact,
        )
