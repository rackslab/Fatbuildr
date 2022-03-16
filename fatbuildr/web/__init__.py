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

from datetime import datetime

from flask import Flask
from flask.helpers import locked_cached_property
from jinja2 import FileSystemLoader

from . import views
from ..log import logr

logger = logr(__name__)


def timestamp_iso(value):
    return datetime.fromtimestamp(value).isoformat(sep=' ', timespec='seconds')


class WebApp(Flask):
    def __init__(self, conf, instance):
        super().__init__('fatbuildr', static_folder=conf.run.static)
        self.conf = conf
        self.instance = instance
        self.add_url_rule('/version', view_func=views.version)

        if self.allinstances:
            self.add_url_rule(
                '/', view_func=views.index, defaults={'output': 'html'}
            )
            self.add_url_rule(
                '/instances.json',
                view_func=views.index,
                defaults={'output': 'json'},
            )

        self.add_instance_url_rule(
            '/instance.json',
            view_func=views.instance,
        )
        self.add_instance_url_rule(
            '/pipelines/formats.json',
            view_func=views.pipelines_formats,
        )
        self.add_instance_url_rule(
            '/registry/',
            view_func=views.registry,
            defaults={'output': 'html'},
        )
        self.add_instance_url_rule(
            '/registry.json',
            view_func=views.registry,
            defaults={'output': 'json'},
        )
        self.add_instance_url_rule(
            '/registry/<string:fmt>/',
            view_func=views.format,
            defaults={'output': 'html'},
        )
        self.add_instance_url_rule(
            '/registry/<string:fmt>.json',
            view_func=views.format,
            defaults={'output': 'json'},
        )
        self.add_instance_url_rule(
            '/registry/<string:fmt>/<string:distribution>/',
            view_func=views.distribution,
            defaults={'output': 'html'},
        )
        self.add_instance_url_rule(
            '/registry/<string:fmt>/<string:distribution>.json',
            view_func=views.distribution,
            defaults={'output': 'json'},
        )
        self.add_instance_url_rule(
            '/registry/<string:fmt>/'
            '<string:distribution>/<string:derivative>/',
            view_func=views.derivative,
            defaults={'output': 'html'},
        )
        self.add_instance_url_rule(
            '/registry/<string:fmt>/'
            '<string:distribution>/<string:derivative>.json',
            view_func=views.derivative,
            defaults={'output': 'json'},
        )
        self.add_instance_url_rule(
            '/registry/<string:fmt>/'
            '<string:distribution>/<string:derivative>/<string:architecture>/'
            '<string:artefact>/',
            view_func=views.artefact,
            defaults={'output': 'html'},
        )
        self.add_instance_url_rule(
            '/registry/<string:fmt>/'
            '<string:distribution>/<string:derivative>/<string:architecture>/'
            '<string:artefact>.json',
            view_func=views.artefact,
            defaults={'output': 'json'},
        )
        self.add_instance_url_rule(
            '/search/<string:artefact>',
            view_func=views.search,
            defaults={'output': 'html'},
        )
        self.add_instance_url_rule(
            '/search/<string:artefact>.json',
            view_func=views.search,
            defaults={'output': 'json'},
        )
        self.add_instance_url_rule(
            '/build',
            view_func=views.build,
            methods=['POST'],
        )
        self.add_instance_url_rule('/running.json', view_func=views.running)
        self.add_instance_url_rule('/queue.json', view_func=views.queue)
        self.add_instance_url_rule(
            '/tasks/<string:task_id>.json',
            view_func=views.task,
        )
        self.add_instance_url_rule(
            '/watch/<string:task_id>.log',
            view_func=views.watch,
        )
        self.add_instance_url_rule('/<path:filename>', view_func=views.content)
        self.add_instance_url_rule('/keyring.asc', view_func=views.keyring)

        self.jinja_env.filters['timestamp_iso'] = timestamp_iso
        self.config['UPLOAD_FOLDER'] = self.conf.dirs.tmp
        self.config['REGISTRY_FOLDER'] = self.conf.dirs.registry
        self.config['INSTANCE'] = self.instance

    @property
    def allinstances(self):
        return self.instance == 'all'

    def add_instance_url_rule(self, path, **kwargs):
        if not self.allinstances:
            if not 'defaults' in kwargs:
                kwargs['defaults'] = {}
            kwargs['defaults']['instance'] = self.instance
            self.add_url_rule(path, **kwargs)
        else:
            self.add_url_rule('/<string:instance>' + path, **kwargs)

    def run(self):
        super().run(host=self.conf.run.host, debug=self.conf.run.debug)

    @locked_cached_property
    def jinja_loader(self):
        """Override Flask Scaffold.jinja_loader() to use Jinja2
        FileSystemLoader with 2 paths: the site templates directory and the
        vendor templates directory.

        Flask does not support natively setting multiple template paths.

        This allows sites to override templates provided by Fatbuilder to
        customize the output of the web app (eg. giving them a more
        corporate look)."""
        return FileSystemLoader(
            [self.conf.run.templates, self.conf.run.vendor_templates]
        )
