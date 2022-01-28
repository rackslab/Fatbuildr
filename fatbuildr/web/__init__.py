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

from flask import Flask

from . import views

class WebApp(Flask):
    def __init__(self, conf):
        super().__init__('fatbuildr',
                         template_folder=conf.run.templates)
        self.conf = conf
        self.add_url_rule('/version', view_func=views.version)
        self.add_url_rule('/', view_func=views.index)
        self.add_url_rule('/<string:instance>/registry/',
                          view_func=views.instance)
        self.add_url_rule('/<string:instance>/registry/<string:fmt>/',
                          view_func=views.distributions)
        self.add_url_rule('/<string:instance>/registry/<string:fmt>/'
                          '<string:distribution>/',
                          view_func=views.registry)
        self.add_url_rule('/<string:instance>/registry/<string:fmt>/'
                          '<string:distribution>/src/<string:artefact>',
                          view_func=views.source_artefact)
        self.add_url_rule('/<string:instance>/registry/<string:fmt>/'
                          '<string:distribution>/bin/<string:artefact>',
                          view_func=views.binary_artefact)
        self.add_url_rule('/<string:instance>/artefacts/<string:artefact>',
                          view_func=views.artefact)
        self.add_url_rule('/queue', view_func=views.queue)

    def run(self):
        super().run(host='0.0.0.0', debug=self.conf.run.debug)
