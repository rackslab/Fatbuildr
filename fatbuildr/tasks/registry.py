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
from ..registry.manager import RegistryManager
from ..log import logr

logger = logr(__name__)


class RegistryArtefactDeletionTask(RunnableTask):
    def __init__(
        self,
        conf,
        instance,
        task_id,
        format,
        distribution,
        derivative,
        artefact,
    ):
        super().__init__(task_id, 'pending')
        self.conf = conf
        self.instance = instance
        self.format = format
        self.distribution = distribution
        self.derivative = derivative
        self.artefact = artefact

    def run(self):
        super().run()
        logger.info(
            "Running artefact deletion task %s %s>%s>%s>%s",
            self.id,
            self.format,
            self.distribution,
            self.derivative,
            self.artefact.name,
        )
        registry_mgr = RegistryManager(self.conf)
        registry_mgr.delete_artefact(
            self.instance.id,
            self.format,
            self.distribution,
            self.derivative,
            self.artefact,
        )

    def terminate(self):
        logger.info(
            "Terminating artefact deletion task %s %s>%s>%s>%s",
            self.id,
            self.format,
            self.distribution,
            self.derivative,
            self.artefact.name,
        )
