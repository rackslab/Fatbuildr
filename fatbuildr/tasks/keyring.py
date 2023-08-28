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
from ..errors import FatbuildrTaskExecutionError, FatbuildrKeyringError

logger = logr(__name__)


class KeyringCreationTask(RunnableTask):

    TASK_NAME = 'keyring creation'
    EXFIELDS = set()

    def __init__(self, task_id, user, place, instance):
        super().__init__(task_id, user, place, instance)

    def run(self):
        logger.info(
            "Running keyring creation task %s",
            self.id,
        )
        try:
            self.instance.keyring.create()
        except FatbuildrKeyringError as err:
            raise FatbuildrTaskExecutionError from err


class KeyringRenewalTask(RunnableTask):

    TASK_NAME = 'keyring renewal'
    EXFIELDS = {
        ExportableTaskField('duration'),
    }

    def __init__(self, task_id, user, place, instance, duration):
        super().__init__(task_id, user, place, instance, duration)
        self.duration = duration

    def run(self):
        logger.info(
            "Running keyring renewal task %s",
            self.id,
        )
        try:
            self.instance.keyring.renew(self.duration)
        except FatbuildrKeyringError as err:
            raise FatbuildrTaskExecutionError from err
