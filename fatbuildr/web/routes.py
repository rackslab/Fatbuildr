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
def index():
    connection = ClientFactory.get()
    instances = connection.instances()
    for mimetype in request.accept_mimetypes:
        if mimetype[0] == 'text/html':
            return render_template('index.html.j2', instances=instances)
        else:
            return jsonify(instances)

@app.route("/<string:instance>/registry/")
def instance(instance):
    connection = ClientFactory.get()
    formats = connection.formats(instance)
    for mimetype in request.accept_mimetypes:
        if mimetype[0] == 'text/html':
            return render_template('instance.html.j2',
                                   instance=instance,
                                   formats=formats)
        else:
            return jsonify(formats)

@app.route("/<string:instance>/registry/<string:fmt>/")
def distributions(instance, fmt):
    connection = ClientFactory.get()
    distributions = connection.distributions(instance, fmt)
    for mimetype in request.accept_mimetypes:
        if mimetype[0] == 'text/html':
            return render_template('format.html.j2',
                                   instance=instance,
                                   format=fmt,
                                   distributions=distributions)
        else:
            return jsonify(distributions)

@app.route('/<string:instance>/registry/<string:fmt>/<string:distribution>/')
def registry(instance, fmt, distribution):
    connection = ClientFactory.get()
    artefacts = connection.artefacts(instance, fmt, distribution)
    for mimetype in request.accept_mimetypes:
        if mimetype[0] == 'text/html':
            return render_template('distribution.html.j2',
                                   instance=instance,
                                   format=fmt,
                                   distribution=distribution,
                                   artefacts=artefacts)
        else:
            return jsonify([vars(artefact) for artefact in artefacts])

@app.route('/<string:instance>/registry/<string:fmt>/<string:distribution>/src/<string:artefact>')
def source_artefact(instance, fmt, distribution, artefact):
    connection = ClientFactory.get()
    artefact_bins = connection.artefact_bins(instance, fmt, distribution, artefact)

    for mimetype in request.accept_mimetypes:
        if mimetype[0] == 'text/html':
            return render_template('src.html.j2',
                                   instance=instance,
                                   format=fmt,
                                   distribution=distribution,
                                   source=artefact,
                                   binaries=artefact_bins)
        else:
            return jsonify(artefact_bins)

@app.route('/<string:instance>/registry/<string:fmt>/<string:distribution>/bin/<string:artefact>')
def binary_artefact(instance, fmt, distribution, artefact):
    connection = ClientFactory.get()
    artefact_src = connection.artefact_src(instance, fmt, distribution, artefact)

    for mimetype in request.accept_mimetypes:
        if mimetype[0] == 'text/html':
            return render_template('bin.html.j2',
                                   instance=instance,
                                   format=fmt,
                                   distribution=distribution,
                                   binary=artefact,
                                   source=artefact_src)
        else:
            return jsonify(artefact_src)

@app.route('/<string:instance>/artefacts/<string:artefact>')
def artefact(instance, artefact):
    connection = ClientFactory.get()
    formats = connection.formats(instance)
    results = {}

    for fmt in formats:
        distributions = connection.distributions(instance, fmt)
        for distribution in distributions:
            artefacts = connection.artefacts(instance, fmt, distribution)
            for _artefact in artefacts:
                if artefact == _artefact.name:
                    if fmt not in results:
                        results[fmt] = {}
                    if distribution not in results[fmt]:
                        results[fmt][distribution] = []
                    results[fmt][distribution].append(_artefact)

    for mimetype in request.accept_mimetypes:
        if mimetype[0] == 'text/html':
            return render_template('artefact.html.j2',
                                   instance=instance,
                                   artefact=artefact,
                                   results=results)
        else:
            return jsonify(results)

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
