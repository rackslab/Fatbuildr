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
import glob

from .. import ArtefactBuild
from ...templates import Templeter
from ...log import logr

logger = logr(__name__)


class ArtefactBuildOsi(ArtefactBuild):
    """Class to manipulate builds of OS images."""

    def __init__(self, conf, build_id, form):
        super().__init__(conf, build_id, form)
        self.format = 'osi'

    def build(self):
        """Build the OS image using mkosi"""

        logger.info("Building the OS image based %s" % (self.name))

        def_path = os.path.join(self.place, self.format, self.name + '.mkosi')
        if not os.path.exists(def_path):
            raise RuntimeError(
                "Unable to find OS image definition file at %s" % (def_path)
            )
        output = os.path.join(self.place, self.name + '.mkosi')

        cmd = [
            'mkosi',
            '--default',
            def_path,
            '--output-dir',
            self.place,
            '--image-id',
            self.name,
            '--image-version',
            self.version,
            '--checksum',
        ]
        self.contruncmd(cmd)

        # Load keyring in agent
        self.keyring.load_agent()

        # Sign checksum file. Note mkosi built-in signature feature (--sign) is
        # not used because, for security reasons, keyring is not available in
        # build container. The checksum file is signed the same way mkosi does
        # (as expected by systemd-importd) outside the build container.
        checksum_path = os.path.join(self.place, 'SHA256SUMS')
        sig_path = checksum_path + '.gpg'
        logger.info("Signing checksum file %s with GPG" % (checksum_path))
        cmd = [
            'gpg',
            '--detach-sign',
            '--output',
            sig_path,
            '--default-key',
            self.keyring.masterkey.userid,
            checksum_path,
        ]
        self.runcmd(cmd, env={'GNUPGHOME': self.keyring.homedir})
