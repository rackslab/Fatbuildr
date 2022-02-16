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

from .formats.deb import ArtefactBuildDeb
from .formats.rpm import ArtefactBuildRpm
from .formats.osi import ArtefactBuildOsi
from .form import BuildForm


class BuildFactory(object):

    _formats = {
        'deb': ArtefactBuildDeb,
        'rpm': ArtefactBuildRpm,
        'osi': ArtefactBuildOsi,
    }

    @staticmethod
    def generate(conf, instance, submission):
        """Generate a BuildArtefact from a new submission."""
        if not submission.format in BuildFactory._formats:
            raise RuntimeError(
                "format %s unsupported by builders" % (submission.format)
            )
        return BuildFactory._formats[submission.format].load_from_submission(
            conf, instance, submission
        )

    @staticmethod
    def load(conf, instance, place, build_id):
        """Load a BuildArtefact based on a format."""
        # Load the form to get the format
        form = BuildForm.load(place)
        if not form.format in BuildFactory._formats:
            raise RuntimeError(
                "format %s unsupported by builders" % (form.format)
            )
        return BuildFactory._formats[form.format](
            conf, instance, build_id, form
        )
