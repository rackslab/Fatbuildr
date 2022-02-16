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

from ..wire import WireInstance, WireBuild
from ...log import logr

logger = logr(__name__)


class HttpClient:
    def __init__(self, host):
        self.host = host

    def instance(self, instance):
        url = f"{self.host}/{instance}/instance.json"
        response = requests.get(url)
        return WireInstance.load_from_json(response.json())

    def pipelines_format_distributions(self, instance, format):
        url = f"{self.host}/{instance}/pipelines/formats.json?format={format}"
        response = requests.get(url)
        formats = response.json()
        return [item['distribution'] for item in formats[format]]

    def pipelines_distribution_format(self, instance, distribution):
        url = f"{self.host}/{instance}/pipelines/formats.json?distribution={distribution}"
        response = requests.get(url)
        formats = response.json()
        return formats.keys()[0]

    def pipelines_distribution_environment(self, instance, distribution):
        url = f"{self.host}/{instance}/pipelines/formats.json?distribution={distribution}"
        response = requests.get(url)
        formats = response.json()
        # Return the environment of the first distribution of the first format,
        # because there is only one format and distribution thanks to the
        # request filter.
        return next(iter(formats.items()))[1][0]['environment']

    def pipelines_derivative_formats(self, instance, derivative):
        url = f"{self.host}/{instance}/pipelines/formats.json?derivative={derivative}"
        response = requests.get(url)
        formats = response.json()
        return list(formats.keys())

    def submit(self, instance, request):
        url = f"{self.host}/{instance}/submit"

        files = {
            'tarball': open(request.tarball, 'rb'),
            'form': open(request.formfile, 'rb'),
        }
        logger.debug("Submitting build request to %s", url)
        response = requests.post(url, files=files)

        # Delete the request files and temporary directory as they are not
        # consumed by the http server.
        request.cleanup()

        return response.json()['build']

    def queue(self, instance):
        url = f"{self.host}/{instance}/queue.json"
        response = requests.get(url)
        return [WireBuild.load_from_json(build) for build in response.json()]

    def running(self, instance):
        url = f"{self.host}/{instance}/running.json"
        response = requests.get(url)
        json_build = response.json()
        if json_build is None:
            return None
        return WireBuild.load_from_json(json_build)

    def get(self, instance, build_id):
        url = f"{self.host}/{instance}/builds/{build_id}.json"
        response = requests.get(url)
        json_build = response.json()
        if json_build is None:
            return None
        return WireBuild.load_from_json(json_build)

    def watch(self, instance, build):
        """Generate build log lines with a streaming request."""
        url = f"{self.host}/{instance}/watch/{build.id}.log"
        response = requests.get(url, stream=True)
        for line in response.iter_lines(decode_unicode=True, delimiter='\n'):
            yield line + '\n'
