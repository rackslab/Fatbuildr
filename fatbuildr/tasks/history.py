#!/usr/bin/env python3
#
# Copyright (C) 2023 Rackslab
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

from ..log import logr

logger = logr(__name__)


class HistoryPurgeTask(RunnableTask):

    TASK_NAME = 'history purge'
    EXFIELDS = set()

    def __init__(self, task_id, user, place, instance):
        super().__init__(task_id, user, place, instance)

    def run(self):
        logger.info(
            "Running history purge task %s",
            self.id,
        )
        self.instance.history_mgr.purge()
