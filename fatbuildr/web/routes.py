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

from flask import Flask, request, jsonify, render_template

from ..version import __version__
from ..protocols import ClientFactory
from ..log import logr

logger = logr(__name__)

app = Flask(__name__, template_folder='/usr/lib/fatbuildr/web/templates')

@app.route("/version")
def version():
    return f"Fatbuildr v{__version__}"

@app.route("/")
def instances():
    connection = ClientFactory.get()
    instances = connection.instances()
    for mimetype in request.accept_mimetypes:
        if mimetype[0] == 'text/html':
            return render_template('index.html.j2', instances=instances)
        else:
            return jsonify(instances)

@app.route('/queue')
def queue():
    connection = ClientFactory.get()
    running = connection.running()
    if running:
        builds = [running]
    else:
        builds = []
    builds.extend(connection.queue())
    return jsonify([vars(build) for build in builds])

@app.route('/<string:instance>/registry/<string:fmt>/<string:distribution>')
def registry(instance, fmt, distribution):
    connection = ClientFactory.get()
    artefacts = connection.registry_distribution(instance, fmt, distribution)
    return jsonify([vars(artefact) for artefact in artefacts])