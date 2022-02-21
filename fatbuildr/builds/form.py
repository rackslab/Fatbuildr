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

import os
import shutil
from datetime import datetime

import yaml

from ..log import logr

logger = logr(__name__)


class BuildForm(object):

    YML_FILE = 'build.yml'

    def __init__(
        self,
        user,
        email,
        distribution,
        derivative,
        fmt,
        artefact,
        submission,
        message,
    ):
        self.user = user
        self.email = email
        self.distribution = distribution
        self.derivative = derivative
        self.format = fmt
        self.artefact = artefact
        self.submission = submission
        self.message = message

    @property
    def filename(self):
        return self.YML_FILE

    def todict(self):
        return {
            'user': self.user,
            'email': self.email,
            'distribution': self.distribution,
            'derivative': self.derivative,
            'format': self.format,
            'artefact': self.artefact,
            'submission': int(self.submission.timestamp()),
            'message': self.message,
        }

    def save(self, dest):
        path = os.path.join(dest, BuildForm.YML_FILE)
        logger.debug("Saving build form in YAML file %s" % (path))
        with open(path, 'w+') as fh:
            yaml.dump(self.todict(), fh)

    def move(self, orig, dest):
        path = os.path.join(orig, BuildForm.YML_FILE)
        logger.debug(
            "Moving YAML build form file %s to directory %s" % (path, dest)
        )
        shutil.move(path, dest)

    @classmethod
    def load(cls, place):
        path = place.joinpath(BuildForm.YML_FILE)
        with open(path, 'r') as fh:
            description = yaml.load(fh, Loader=yaml.FullLoader)
        return cls(
            description['user'],
            description['email'],
            description['distribution'],
            description['derivative'],
            description['format'],
            description['artefact'],
            datetime.fromtimestamp(description['submission']),
            description['message'],
        )
