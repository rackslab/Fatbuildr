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

import tempfile

from datetime import datetime

from ..builds import BuildRequest
from ..log import logr

logger = logr(__name__)


class ClientBuildsManager:
    def __init__(self, conf):
        self.conf = conf

    def request(
        self,
        basedir,
        subdir,
        distribution,
        derivative,
        artefact,
        fmt,
        user_name,
        user_email,
        msg,
    ):
        # create tmp submission directory
        tmpdir = tempfile.mkdtemp(prefix='fatbuildr', dir=self.conf.dirs.tmp)
        logger.debug("Created request temporary directory %s" % (tmpdir))

        # create build request
        request = BuildRequest(
            tmpdir,
            user_name,
            user_email,
            distribution,
            derivative,
            fmt,
            artefact,
            datetime.now(),
            msg,
        )

        # save the request form in tmpdir
        request.form.save(tmpdir)

        # prepare artefact tarball
        request.prepare_tarball(basedir, subdir, tmpdir)
        return request
