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
from ..log import logr

logger = logr(__name__)


class ImageCreationTask(RunnableTask):

    TASK_NAME = 'image creation'
    EXFIELDS = {
        ExportableTaskField('format'),
        ExportableTaskField('force', bool),
    }

    def __init__(self, task_id, place, instance, format, force):
        super().__init__(task_id, place, instance)
        self.format = format
        self.force = force

    def run(self):
        logger.info(
            "Running image creation task %s",
            self.id,
        )
        self.instance.images_mgr.create(self.format, self.force)
