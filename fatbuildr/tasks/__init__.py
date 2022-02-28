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

from pathlib import Path
from datetime import datetime

from ..protocols.exports import ExportableTaskField
from ..utils import runcmd
from ..log import logr

logger = logr(__name__)


class RunnableTask:
    """Abtract runnable task."""

    BASEFIELDS = {
        ExportableTaskField('id', archived=False),
        ExportableTaskField('name'),
        ExportableTaskField('submission', datetime),
        ExportableTaskField('place', Path, archived=False),
        ExportableTaskField('state', archived=False),
        ExportableTaskField('logfile', Path, archived=False),
    }

    def __init__(
        self,
        task_id,
        place,
        instance,
        state='pending',
        submission=datetime.now(),
    ):
        self.name = self.TASK_NAME
        self.id = task_id
        self.place = place
        self.instance = instance
        self.state = state
        self.submission = submission
        self.log = None  # handler on logfile, opened in run()

    @property
    def logfile(self):
        if self.place is None or self.state not in ['running', 'finished']:
            return None
        return self.place.joinpath('task.log')

    def prerun(self):
        self.state = 'running'

        if self.place.exists():
            logger.warning("Task directory %s already exists", self.place)
        else:
            # create build directory
            logger.info("Creating task directory %s", self.place)
            self.place.mkdir()
            self.place.chmod(0o755)  # be umask agnostic

        self.log = open(self.logfile, 'w+')

        # setup logger to duplicate logs in logfile
        logger.add_file(self.log, self.instance.id)

    def run(self):
        raise NotImplementedError

    def postrun(self):

        logger.del_file()
        self.log.close()

    def terminate(self):
        self.instance.archives_mgr.save_task(self)

    def runcmd(self, cmd, **kwargs):
        """Run command locally and log output in build log file."""
        runcmd(cmd, log=self.log, **kwargs)

    def cruncmd(self, image, cmd, init=False, **kwargs):
        """Run command in container and log output in build log file."""
        self.instance.crun.run(image, cmd, init=init, log=self.log, **kwargs)
