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

import glob

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
            '--default',
            str(def_path),
            '--output-dir',
            str(self.place),
            '--image-id',
            self.artifact,
            '--image-version',
            self.version.main,
            '--checksum',
        ]
        # mkosi requires being run as root
        self.cruncmd(cmd, asroot=True)

        # Load keyring in agent
        self.instance.keyring.load_agent()

        # Sign checksum file. Note mkosi built-in signature feature (--sign) is
        # not used because, for security reasons, keyring is not available in
        # build container. The checksum file is signed the same way mkosi does
        # (as expected by systemd-importd) outside the build container.
        checksum_path = self.place.joinpath('SHA256SUMS')
        sig_path = checksum_path.with_suffix('.gpg')
        logger.info("Signing checksum file %s with GPG", checksum_path)
        cmd = [
            'gpg',
            '--detach-sign',
            '--output',
            str(sig_path),
            '--default-key',
            self.instance.keyring.masterkey.userid,
            str(checksum_path),
        ]
        self.runcmd(cmd, env={'GNUPGHOME': str(self.instance.keyring.homedir)})
