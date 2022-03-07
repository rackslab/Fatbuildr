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


class ArtefactBuildRpm(ArtefactBuild):
    """Class to manipulation package in RPM format."""

    def __init__(
        self,
        task_id,
        place,
        instance,
        conf,
        format,
        distribution,
        derivative,
        artefact,
        user_name,
        user_email,
        message,
        tarball,
    ):
        super().__init__(
            task_id,
            place,
            instance,
            conf,
            format,
            distribution,
            derivative,
            artefact,
            user_name,
            user_email,
            message,
            tarball,
        )
        self.format = 'rpm'

    @property
    def spec_basename(self):
        return self.artefact + '.spec'

    @property
    def srpm_filename(self):
        return self.artefact + '-' + self.version.full + '.src.rpm'

    @property
    def srpm_path(self):
        return self.place.joinpath(self.srpm_filename)

    def build(self):
        self._build_src()
        self._build_bin()

    def _build_src(self):
        """Build source SRPM"""

        logger.info(
            "Building source RPM for %s in environment %s",
            self.artefact,
            self.env.name,
        )

        # Add distribution to targeted version
        self.version.dist = self.distribution

        # Generate spec file base on template
        spec_tpl_path = self.place.joinpath('rpm', self.spec_basename)
        spec_path = self.place.joinpath(self.spec_basename)

        if not spec_tpl_path.exists():
            raise RuntimeError(
                f"RPM spec template file {spec_tpl_path} does not exist"
            )

        logger.debug(
            "Generate RPM spec file %s based on %s", spec_path, spec_tpl_path
        )
        with open(spec_path, 'w+') as fh:
            fh.write(
                Templeter().frender(
                    spec_tpl_path,
                    pkg=self,
                    version=self.version.main,
                    release=self.version.fullrelease,
                )
            )

        # run SRPM build
        cmd = [
            'mock',
            '--root',
            self.env.name,
            '--buildsrpm',
            '--sources',
            self.cache.dir,
            '--spec',
            str(spec_path),
            '--resultdir',
            str(self.place),
        ]
        self.cruncmd(cmd)

    def _build_bin(self):
        """Build binary RPM"""

        logger.info(
            "Building binary RPM based on %s in environment %s",
            self.srpm_path,
            self.env.name,
        )

        # Save keyring in build place so dnf can check signatures of
        # fatbuildr packages in mock environment.
        keyring_path = self.place.joinpath('keyring.asc')
        with open(keyring_path, 'w+') as fh:
            fh.write(self.instance.keyring.export())

        cmd = [
            'mock',
            '--root',
            self.env.name,
            '--enable-plugin',
            'fatbuildr_derivatives',
            '--plugin-option',
            f"fatbuildr_derivatives:repo={self.registry.path}",
            '--plugin-option',
            f"fatbuildr_derivatives:distribution={self.distribution}",
            '--plugin-option',
            f"fatbuildr_derivatives:derivatives={','.join(self.derivatives)}",
            '--plugin-option',
            f"fatbuildr_derivatives:keyring={str(keyring_path)}",
            '--resultdir',
            str(self.place),
            '--rebuild',
            str(self.srpm_path),
        ]

        # Add additional build args if defined
        if self.has_buildargs:
            cmd.extend(self.buildargs)

        self.cruncmd(cmd)

        # Load keys in agent prior to signing
        self.instance.keyring.load_agent()

        # sign all RPM packages, including SRPM
        for rpm_path in self.place.glob('*.rpm'):
            logger.debug(
                "Signing RPM %s with key %s",
                rpm_path,
                self.instance.keyring.masterkey.fingerprint,
            )
            cmd = [
                'rpmsign',
                '--define',
                '%__gpg /usr/bin/gpg',
                '--define',
                '%_gpg_name ' + self.instance.keyring.masterkey.userid,
                '--addsign',
                str(rpm_path),
            ]
            self.runcmd(cmd, env={'GNUPGHOME': self.instance.keyring.homedir})
