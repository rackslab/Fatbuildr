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
        instance,
        task_id,
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
            instance,
            task_id,
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
    def release(self):
        # suffix artefact release with distribution
        return super().release + '.' + self.distribution

    @property
    def spec_basename(self):
        return self.artefact + '.spec'

    @property
    def srpm_filename(self):
        return (
            self.artefact + '-' + self.version + '-' + self.release + '.src.rpm'
        )

    @property
    def srpm_path(self):
        return os.path.join(self.place, self.srpm_filename)

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

        # Generate spec file base on template
        spec_tpl_path = os.path.join(self.place, 'rpm', self.spec_basename)
        spec_path = os.path.join(self.place, self.spec_basename)

        if not os.path.exists(spec_tpl_path):
            raise RuntimeError(
                f"RPM spec template file {spec_tpl_path} does not exist"
            )

        logger.debug(
            "Generate RPM spec file %s based on %s" % (spec_path, spec_tpl_path)
        )
        with open(spec_path, 'w+') as fh:
            fh.write(Templeter.frender(spec_tpl_path, pkg=self))

        # run SRPM build
        cmd = [
            'mock',
            '--root',
            self.env.name,
            '--buildsrpm',
            '--sources',
            self.cache.dir,
            '--spec',
            spec_path,
            '--resultdir',
            self.place,
        ]
        self.contruncmd(cmd)

    def _build_bin(self):
        """Build binary RPM"""

        logger.info(
            "Building binary RPM based on %s in environment %s"
            % (self.srpm_path, self.env.name)
        )

        # Save keyring in build place so dnf can check signatures of
        # fatbuildr packages in mock environment.
        keyring_path = os.path.join(self.place, 'keyring.asc')
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
            f"fatbuildr_derivatives:keyring={keyring_path}",
            '--resultdir',
            self.place,
            '--rebuild',
            self.srpm_path,
        ]

        # Add additional build args if defined
        if self.has_buildargs:
            cmd.extend(self.buildargs)

        self.contruncmd(cmd)

        # Load keys in agent prior to signing
        self.instance.keyring.load_agent()

        # sign all RPM packages, including SRPM
        rpm_glob = os.path.join(self.place, '*.rpm')
        for rpm_path in glob.glob(rpm_glob):
            logger.debug(
                "Signing RPM %s with key %s"
                % (rpm_path, self.instance.keyring.masterkey.fingerprint)
            )
            cmd = [
                'rpmsign',
                '--define',
                '%__gpg /usr/bin/gpg',
                '--define',
                '%_gpg_name ' + self.instance.keyring.masterkey.userid,
                '--addsign',
                rpm_path,
            ]
            self.runcmd(cmd, env={'GNUPGHOME': self.instance.keyring.homedir})
