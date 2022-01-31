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

import requests

from ..wire import WireBuild
from ...log import logr

logger = logr(__name__)


class HttpClient:

    def __init__(self, host):
        self.host = host

    def submit(self, request):
        url=f"{self.host}/submit"

        files={'tarball': open(request.tarball,'rb'),
               'form': open(request.formfile,'rb')}
        logger.debug("Submitting build request to %s", url)
        response = requests.post(url, files=files)

        # Delete the request files and temporary directory as they are not
        # consumed by the http server.
        request.cleanup()

        return response.json()['build']

    def queue(self):
        url=f"{self.host}/queue.json"
        response = requests.get(url)
        return [WireBuild.load_from_json(build) for build in response.json()]

    def running(self):
        url=f"{self.host}/running.json"
        response = requests.get(url)
        json_build = response.json()
        if json_build is None:
            return None
        return WireBuild.load_from_json(json_build)
