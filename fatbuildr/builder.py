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

from .builders.deb import BuilderArtefactDeb
from .builders.rpm import BuilderArtefactRpm


class BuilderFactory(object):

    _builders = {
        'deb': BuilderArtefactDeb,
        'rpm': BuilderArtefactRpm,
    }

    @staticmethod
    def builder(conf, job, tmpdir):
        if not job.format in BuilderFactory._builders:
            raise RuntimeError("format %s unsupported by builders" % (job.format))
        return BuilderFactory._builders[job.format](conf, job, tmpdir)
