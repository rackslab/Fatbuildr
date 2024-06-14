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

from .. import ArtifactBuild
from ...log import logr

logger = logr(__name__)


class ArtifactBuildOsi(ArtifactBuild):
    """Class to manipulate builds of OS images."""

    def __init__(
        self,
        task_id,
        user,
        place,
        instance,
        format,
        distribution,
        architectures,
        derivative,
        artifact,
        author,
        email,
        message,
        tarball,
        sources,
        interactive,
    ):
        super().__init__(
            task_id,
            user,
            place,
            instance,
            format,
            distribution,
            architectures,
            derivative,
            artifact,
            author,
            email,
            message,
            tarball,
            sources,
            interactive,
        )

    def build(self):
        """Build the OS image using mkosi"""

        logger.info("Building the OS image based %s", self.artifact)

        def_path = self.place.joinpath(self.format, self.artifact + '.mkosi')
        if not def_path.exists():
            raise RuntimeError(
                f"Unable to find OS image definition file at {def_path}"
            )

        cmd = [
            self.image.builder,
            '--directory',
            self.place.joinpath(self.format),
            '--package-cache-dir',
            self.cache.dir,
            '--workspace-dir',
            str(self.place),
            '--include',
            str(def_path),
            '--output-dir',
            str(self.place),
            '--image-id',
            self.artifact,
            '--image-version',
            self.version.main,
            '--checksum',
            'build',
        ]
        if self.image.format_conf.containerized:
            self.cruncmd(cmd)
        else:
            self.runcmd(
                cmd,
                env={
                    'SUDO_UID': str(os.getuid()),
                    'PATH': f"{os.getenv('PATH')}:/bin:/sbin",
                },
            )
