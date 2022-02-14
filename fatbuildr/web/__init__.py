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
    def __init__(self, conf):
        super().__init__('fatbuildr')
        self.conf = conf
        self.add_url_rule('/version', view_func=views.version)
        self.add_url_rule(
            '/<instance>/instance.json',
            view_func=views.instance,
        )
        self.add_url_rule(
            '/<instance>/pipelines/formats.json',
            view_func=views.pipelines_formats,
        )
        self.add_url_rule('/', view_func=views.index)
        self.add_url_rule(
            '/instances.json',
            view_func=views.index,
            defaults={'output': 'json'},
        )
        self.add_url_rule(
            '/<string:instance>/registry/', view_func=views.registry_formats
        )
        self.add_url_rule(
            '/<string:instance>/registry.json',
            view_func=views.registry_formats,
            defaults={'output': 'json'},
        )
        self.add_url_rule(
            '/<string:instance>/registry/<string:fmt>/',
            view_func=views.format_distributions,
        )
        self.add_url_rule(
            '/<string:instance>/registry/<string:fmt>.json',
            view_func=views.format_distributions,
            defaults={'output': 'json'},
        )
        self.add_url_rule(
            '/<string:instance>/registry/<string:fmt>/'
            '<string:distribution>/',
            view_func=views.distribution_derivatives,
        )
        self.add_url_rule(
            '/<string:instance>/registry/<string:fmt>/'
            '<string:distribution>.json',
            view_func=views.distribution_derivatives,
            defaults={'output': 'json'},
        )
        self.add_url_rule(
            '/<string:instance>/registry/<string:fmt>/'
            '<string:distribution>/<string:derivative>/',
            view_func=views.derivative_artefacts,
        )
        self.add_url_rule(
            '/<string:instance>/registry/<string:fmt>/'
            '<string:distribution>/<string:derivative>.json',
            view_func=views.derivative_artefacts,
            defaults={'output': 'json'},
        )
        self.add_url_rule(
            '/<string:instance>/registry/<string:fmt>/'
            '<string:distribution>/<string:derivative>/<string:architecture>/'
            '<string:artefact>/',
            view_func=views.artefact,
        )
        self.add_url_rule(
            '/<string:instance>/registry/<string:fmt>/'
            '<string:distribution>/<string:derivative>/<string:architecture>/'
            '<string:artefact>.json',
            view_func=views.artefact,
            defaults={'output': 'json'},
        )
        self.add_url_rule(
            '/<string:instance>/artefacts/<string:artefact>',
            view_func=views.artefacts,
        )
        self.add_url_rule(
            '/<string:instance>/artefacts/<string:artefact>.json',
            view_func=views.artefacts,
            defaults={'output': 'json'},
        )

        self.add_url_rule('/submit', view_func=views.submit, methods=['POST'])
        self.add_url_rule('/running.json', view_func=views.running)
        self.add_url_rule('/queue.json', view_func=views.queue)
        self.add_url_rule(
            '/builds/<string:build_id>.json', view_func=views.build
        )
        self.add_url_rule('/watch/<string:build_id>.log', view_func=views.watch)
        self.add_url_rule(
            '/<string:instance>/<path:filename>', view_func=views.content
        )
        self.add_url_rule(
            '/<string:instance>/keyring.asc', view_func=views.keyring
        )

        self.jinja_env.filters['timestamp_iso'] = timestamp_iso
        self.config['UPLOAD_FOLDER'] = self.conf.dirs.tmp
        self.config['REGISTRY_FOLDER'] = self.conf.dirs.registry

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
