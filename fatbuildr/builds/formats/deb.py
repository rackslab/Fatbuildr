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
import mimetypes
import tarfile
import shutil

from .. import ArtefactBuild
from ...log import logr

logger = logr(__name__)


class ArtefactBuildDeb(ArtefactBuild):
    """Class to manipulation build of package in Deb format."""

    def __init__(self, conf, instance, build_id, form):
        super().__init__(conf, instance, build_id, form)
        self.format = 'deb'

    @property
    def tarball_ext(self):
        # Dicts to map mimetype encoding to tarfile.open() options and orig
        # symlink source extension.
        exts = {
            'bzip2': 'bz2',
            'gzip': 'gz',
            'xz': 'xz',
        }
        return exts[mimetypes.guess_type(self.cache.tarball_path)[1]]

    def build(self):
        self._build_src()
        self._build_bin()

    def _build_src(self):
        """Build deb source package."""

        logger.info(
            "Building source Deb packages for %s in %s"
            % (self.name, self.env.name)
        )

        # extract tarball in build place
        logger.debug(
            "Extracting tarball %s in %s"
            % (self.cache.tarball_path, self.place)
        )
        tar = tarfile.open(self.cache.tarball_path, 'r:' + self.tarball_ext)
        tarball_subdir_info = tar.getmembers()[0]
        if not tarball_subdir_info.isdir():
            raise RuntimeError(
                "unable to define tarball %s subdirectory"
                % (self.cache.tarball_path)
            )
        tarball_subdir = os.path.join(self.place, tarball_subdir_info.name)
        tar.extractall(path=self.place)
        tar.close()

        # copy debian dir
        deb_code_from = os.path.join(self.place, 'deb')
        deb_code_to = os.path.join(tarball_subdir, 'debian')
        logger.debug(
            "Copying debian packaging code from %s into %s"
            % (deb_code_from, deb_code_to)
        )
        shutil.copytree(deb_code_from, deb_code_to)

        # generate changelog
        logger.info("Generating changelog")
        cmd = [
            'debchange',
            '--create',
            '--package',
            self.name,
            '--newversion',
            self.fullversion,
            '--distribution',
            self.distribution,
            self.message,
        ]
        _envs = ['DEBEMAIL=' + self.email, 'DEBFULLNAME=' + self.user]
        self.contruncmd(cmd, chdir=tarball_subdir, envs=_envs)

        #  add symlink to tarball
        orig_tarball_path = os.path.join(
            self.place,
            f"{self.name}_{self.version}.orig.tar.{self.tarball_ext}",
        )
        logger.debug(
            "Creating symlink %s → %s"
            % (orig_tarball_path, self.cache.tarball_path)
        )
        os.symlink(self.cache.tarball_path, orig_tarball_path)

        # build source package
        logger.info("Building source package")
        cmd = ['dpkg-source', '--build', tarball_subdir]
        self.contruncmd(cmd, chdir=self.place)

    def _build_bin(self):
        """Build deb packages binary package."""
        logger.info(
            "Building binary Deb packages for %s in %s"
            % (self.name, self.env.name)
        )

        # Save keyring in build place to cowbuilder can check signatures of
        # fatbuildr repositories.
        keyring_path = os.path.join(self.place, 'keyring.asc')
        with open(keyring_path, 'w+') as fh:
            fh.write(self.keyring.export())

        dsc_path = os.path.join(
            self.place, self.name + '_' + self.fullversion + '.dsc'
        )
        cmd = [
            'cowbuilder',
            '--build',
            '--hookdir',
            '/usr/lib/fatbuildr/images/deb/hooks',
            '--distribution',
            self.distribution,
            '--bindmounts',
            self.place,  # for local repos keyring
            '--basepath',
            '/var/cache/pbuilder/' + self.distribution,
            '--buildresult',
            self.place,
            dsc_path,
        ]

        # The deb registry does not exist until the first artefact is actually
        # published. If it exists, bind-mount so the local repos can be used
        # in cowbuilder environments.
        if self.registry.exists:
            cmd[6:6] = ['--bindmounts', self.registry.path]

        self.contruncmd(
            cmd,
            envs=[
                f"FATBUILDR_REPO={self.registry.path}",
                f"FATBUILDR_KEYRING={keyring_path}",
                f"FATBUILDR_SOURCE={self._instance.name}",
                f"FATBUILDR_DERIVATIVES={' '.join(self.derivatives[::-1])}",
            ],
        )
