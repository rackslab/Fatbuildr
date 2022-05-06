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
from ..client import AbstractClient
from ...log import logr

logger = logr(__name__)


class HttpClient(AbstractClient):
    def __init__(self, uri, scheme, instance):
        super().__init__(uri, scheme, instance)

    def instance(self):
        url = f"{self.uri}/instance.json"
        response = requests.get(url)
        return JsonInstance.load_from_json(response.json())

    def pipelines_architectures(self):
        url = f"{self.uri}/pipelines/architectures.json"
        response = requests.get(url)
        return response.json()

    def pipelines_format_distributions(self, format):
        url = f"{self.uri}/pipelines/formats.json?format={format}"
        response = requests.get(url)
        formats = response.json()
        return [item['distribution'] for item in formats[format]]

    def pipelines_distribution_format(self, distribution):
        url = f"{self.uri}/pipelines/formats.json?distribution={distribution}"
        response = requests.get(url)
        formats = response.json()
        return list(formats.keys())[0]

    def pipelines_distribution_environment(self, distribution):
        url = f"{self.uri}/pipelines/formats.json?distribution={distribution}"
        response = requests.get(url)
        formats = response.json()
        # Return the environment of the first distribution of the first format,
        # because there is only one format and distribution thanks to the
        # request filter.
        return next(iter(formats.items()))[1][0]['environment']

    def pipelines_derivative_formats(self, derivative):
        url = f"{self.uri}/pipelines/formats.json?derivative={derivative}"
        response = requests.get(url)
        formats = response.json()
        return list(formats.keys())

    def build(
        self,
        format,
        distribution,
        architectures,
        derivative,
        artifact,
        user_name,
        user_email,
        message,
        tarball,
        source_tarball,
        interactive,
    ):
        url = f"{self.uri}/build"
        logger.debug("Submitting build request to %s", url)

        files = {'tarball': open(tarball, 'rb')}
        if source_tarball:
            files['source'] = open(source_tarball, 'rb')

        response = requests.post(
            url,
            data={
                'format': format,
                'distribution': distribution,
                'architectures': ','.join(architectures),
                'derivative': derivative,
                'artifact': artifact,
                'user_name': user_name,
                'user_email': user_email,
                'message': message,
            },
            files=files,
        )

        # Delete the tarball (and the source tarball if defined) as it is not
        # accessed by the http server.
        tarball.unlink()

        if source_tarball:
            source_tarball.unlink()

        return response.json()['task']

    def queue(self):
        url = f"{self.uri}/queue.json"
        response = requests.get(url)
        return [
            JsonRunnableTask.load_from_json(task) for task in response.json()
        ]

    def running(self):
        url = f"{self.uri}/running.json"
        response = requests.get(url)
        json_task = response.json()
        if json_task is None:
            return None
        return JsonRunnableTask.load_from_json(json_task)

    def get(self, task_id):
        url = f"{self.uri}/tasks/{task_id}.json"
        response = requests.get(url)
        json_task = response.json()
        if json_task is None:
            return None
        return JsonRunnableTask.load_from_json(json_task)

    def attach(self, task):
        raise NotImplementedError(
            "Attaching to remote task console is not supported with HTTP "
            "instances"
        )

    def watch(self, task):
        """Generate task log lines with a streaming request."""
        url = f"{self.uri}/watch/{task.id}.log"
        response = requests.get(url, stream=True)
        for line in response.iter_lines(decode_unicode=True, delimiter='\n'):
            yield line + '\n'
