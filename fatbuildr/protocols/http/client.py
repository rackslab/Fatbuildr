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

# External requests library can use simplejson when available, with fallback to
# standard json library. This module may receive JSONDecodeError from this
# package, or from the standard library. Adopt the same import logic to catch
# the correct error.
try:
    from simplejson import JSONDecodeError
except ImportError:
    from json import JSONDecodeError

from . import JsonInstance, JsonRunnableTask, JsonArtifact
from ..client import AbstractClient
from ...errors import FatbuildrServerError, FatbuildrServerPermissionError
from ...log import logr
from ...console.client import console_http_client

logger = logr(__name__)


def check_http_errors(method):
    """Decorator for HttpClient methods to catch requests errors and transform
    them into generic Fatbuildr errors.
    """

    def error_handler_wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except requests.exceptions.ConnectionError as err:
            raise FatbuildrServerError(
                f"unable to connect to {args[0].uri}: {err}"
            )
        except JSONDecodeError as err:
            raise FatbuildrServerError(
                f"unable to decode JSON response to {args[0].uri}: {err}"
            )

    return error_handler_wrapper


class HttpClient(AbstractClient):
    def __init__(self, uri, scheme, token):
        super().__init__(uri, scheme)
        self.token = token

    @property
    def headers(self):
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        else:
            return None

    def _auth_request(self, call, *args, **kwargs):
        if 'headers' in kwargs:
            kwargs['headers'].update(self.headers)
        else:
            kwargs['headers'] = self.headers
        response = call(*args, **kwargs)
        if response.status_code == 403:
            raise FatbuildrServerPermissionError(
                f"{response.json()['error']} (403)"
            )
        if response.status_code == 404:
            raise FatbuildrServerError(f"{response.json()['error']} (404)")
        if response.status_code == 500:
            raise FatbuildrServerError("Remote server internal error (500)")
        return response

    @check_http_errors
    def instance(self):
        url = f"{self.uri}/instance.json"
        response = self._auth_request(requests.get, url)
        return JsonInstance.load_from_json(response.json())

    @check_http_errors
    def pipelines_architectures(self):
        url = f"{self.uri}/pipelines/architectures.json"
        response = self._auth_request(requests.get, url)
        return response.json()

    @check_http_errors
    def pipelines_format_distributions(self, format):
        url = f"{self.uri}/pipelines/formats.json?format={format}"
        response = self._auth_request(requests.get, url)
        formats = response.json()
        return [item['distribution'] for item in formats[format]]

    @check_http_errors
    def pipelines_distribution_format(self, distribution):
        url = f"{self.uri}/pipelines/formats.json?distribution={distribution}"
        response = self._auth_request(requests.get, url)
        formats = response.json()
        return list(formats.keys())[0]

    @check_http_errors
    def pipelines_distribution_environment(self, distribution):
        url = f"{self.uri}/pipelines/formats.json?distribution={distribution}"
        response = self._auth_request(requests.get, url)
        formats = response.json()
        # Return the environment of the first distribution of the first format,
        # because there is only one format and distribution thanks to the
        # request filter.
        return next(iter(formats.items()))[1][0]['environment']

    @check_http_errors
    def pipelines_derivative_formats(self, derivative):
        url = f"{self.uri}/pipelines/formats.json?derivative={derivative}"
        response = self._auth_request(requests.get, url)
        formats = response.json()
        return list(formats.keys())

    @check_http_errors
    def artifacts(self, fmt, distribution, derivative):
        url = f"{self.uri}/registry/{fmt}/{distribution}/{derivative}.json"
        response = self._auth_request(requests.get, url)
        artifacts = response.json()
        return [JsonArtifact.load_from_json(item) for item in artifacts]

    @check_http_errors
    def delete_artifact(self, fmt, distribution, derivative, artifact):
        url = (
            f"{self.uri}/registry/{fmt}/{distribution}/{derivative}/"
            "{artifact.architecture}/{artifact.name}.json?"
            "version={artifact.version}"
        )
        response = self._auth_request(requests.delete, url)
        return response.json()['task']

    @check_http_errors
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
        sources,
        interactive,
    ):
        url = f"{self.uri}/build"
        logger.debug("Submitting build request to %s", url)

        files = {'tarball': open(tarball, 'rb')}
        for source in sources:
            files[f"source/{source.id}"] = open(source.path, 'rb')

        # Add cleanup routine in finally clause and reraise the exception for
        # handling in decorator in case of error with HTTP request.
        try:
            response = self._auth_request(
                requests.post,
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
        except Exception:
            raise
        finally:
            # Delete the tarball and the source tarball if defined as they are
            # not accessed by the http server.
            logger.debug("Removing tarball %s", tarball)
            tarball.unlink()
            for source in sources:
                logger.debug("Removing source tarball %s", source.path)
                source.path.unlink()

        return response.json()['task']

    @check_http_errors
    def queue(self):
        url = f"{self.uri}/queue.json"
        response = self._auth_request(requests.get, url)
        return [
            JsonRunnableTask.load_from_json(task) for task in response.json()
        ]

    @check_http_errors
    def running(self):
        url = f"{self.uri}/running.json"
        response = self._auth_request(requests.get, url)
        json_task = response.json()
        if json_task is None:
            return None
        return JsonRunnableTask.load_from_json(json_task)

    @check_http_errors
    def get(self, task_id):
        url = f"{self.uri}/tasks/{task_id}.json"
        response = self._auth_request(requests.get, url)
        json_task = response.json()
        if json_task is None:
            return None
        return JsonRunnableTask.load_from_json(json_task)

    def attach(self, task):
        raise NotImplementedError(
            "Attaching to remote task console is not supported with HTTP "
            "instances"
        )

    @check_http_errors
    def watch(self, task):
        """Generate task log lines with a streaming request."""
        url = f"{self.uri}/watch/{task.id}.journal"
        response = self._auth_request(requests.get, url, stream=True)
        return console_http_client(response)
