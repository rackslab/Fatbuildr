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

from .formats.deb import ArtifactBuildDeb
from .formats.rpm import ArtifactBuildRpm
from .formats.osi import ArtifactBuildOsi


class BuildFactory(object):

    _formats = {
        'deb': ArtifactBuildDeb,
        'rpm': ArtifactBuildRpm,
        'osi': ArtifactBuildOsi,
    }

    @staticmethod
    def generate(
        task_id,
        place,
        instance,
        format,
        distribution,
        architectures,
        derivative,
        artifact,
        user_name,
        user_email,
        message,
        tarball,
        src_tarball,
    ):
        """Generate a BuildArtifact from a new request."""
        if not format in BuildFactory._formats:
            raise RuntimeError(f"format {format} unsupported by builders")
        return BuildFactory._formats[format](
            task_id,
            place,
            instance,
            format,
            distribution,
            architectures,
            derivative,
            artifact,
            user_name,
            user_email,
            message,
            tarball,
            src_tarball,
        )
