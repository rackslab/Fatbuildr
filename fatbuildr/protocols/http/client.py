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

from . import JsonInstance, JsonRunnableTask
from ...log import logr

logger = logr(__name__)


class HttpClient:
    def __init__(self, host):
        self.host = host

    def instance(self, instance):
        url = f"{self.host}/{instance}/instance.json"
        response = requests.get(url)
        return JsonInstance.load_from_json(response.json())

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

    def submit(
        self,
        instance,
        format,
        distribution,
        derivative,
        artefact,
        user_name,
        user_email,
        message,
        tarball,
    ):
        url = f"{self.host}/{instance}/submit"
        logger.debug("Submitting build request to %s", url)
        response = requests.post(
            url,
            data={
                'format': format,
                'distribution': distribution,
                'derivative': derivative,
                'artefact': artefact,
                'user_name': user_name,
                'user_email': user_email,
                'message': message,
            },
            files={
                'tarball': open(tarball, 'rb'),
            },
        )

        # Delete the tarball as it is not accessed by the http server.
        tarball.unlink()

        return response.json()['task']

    def queue(self, instance):
        url = f"{self.host}/{instance}/queue.json"
        response = requests.get(url)
        return [
            JsonRunnableTask.load_from_json(task) for task in response.json()
        ]

    def running(self, instance):
        url = f"{self.host}/{instance}/running.json"
        response = requests.get(url)
        json_task = response.json()
        if json_task is None:
            return None
        return JsonRunnableTask.load_from_json(json_task)

    def get(self, instance, task_id):
        url = f"{self.host}/{instance}/tasks/{task_id}.json"
        response = requests.get(url)
        json_task = response.json()
        if json_task is None:
            return None
        return JsonRunnableTask.load_from_json(json_task)

    def watch(self, instance, task):
        """Generate task log lines with a streaming request."""
        url = f"{self.host}/{instance}/watch/{task.id}.log"
        response = requests.get(url, stream=True)
        for line in response.iter_lines(decode_unicode=True, delimiter='\n'):
            yield line + '\n'
