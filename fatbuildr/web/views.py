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

import os
import tempfile

from flask import request, jsonify, render_template, current_app
from werkzeug.utils import secure_filename

from ..version import __version__
from ..protocols import ClientFactory
from ..builds import BuildRequest


def version():
    return f"Fatbuildr v{__version__}"

def index():
    connection = ClientFactory.get('local')
    instances = connection.instances()
    for mimetype in request.accept_mimetypes:
        if mimetype[0] == 'text/html':
            return render_template('index.html.j2', instances=instances)
        else:
            return jsonify(instances)

def instance(instance):
    connection = ClientFactory.get('local')
    formats = connection.formats(instance)
    for mimetype in request.accept_mimetypes:
        if mimetype[0] == 'text/html':
            return render_template('instance.html.j2',
                                   instance=instance,
                                   formats=formats)
        else:
            return jsonify(formats)

def distributions(instance, fmt):
    connection = ClientFactory.get('local')
    distributions = connection.distributions(instance, fmt)
    for mimetype in request.accept_mimetypes:
        if mimetype[0] == 'text/html':
            return render_template('format.html.j2',
                                   instance=instance,
                                   format=fmt,
                                   distributions=distributions)
        else:
            return jsonify(distributions)

def registry(instance, fmt, distribution):
    connection = ClientFactory.get('local')
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

def artefact(instance, fmt, distribution, architecture, artefact):
    connection = ClientFactory.get('local')
    if architecture == 'src':
        source = None
        binaries = connection.artefact_bins(instance, fmt, distribution, artefact)
        template = 'src.html.j2'
    else:
        source = connection.artefact_src(instance, fmt, distribution, artefact)
        binaries = []
        template = 'bin.html.j2'
    changelog = connection.changelog(instance, fmt, distribution, architecture, artefact)

    for mimetype in request.accept_mimetypes:
        if mimetype[0] == 'text/html':
            return render_template(template,
                                   instance=instance,
                                   format=fmt,
                                   distribution=distribution,
                                   architecture=architecture,
                                   artefact=artefact,
                                   source=source,
                                   binaries=binaries,
                                   changelog=changelog)
        else:
            return jsonify(artefact)

def artefacts(instance, artefact):
    connection = ClientFactory.get('local')
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
            return render_template('artefacts.html.j2',
                                   instance=instance,
                                   artefact=artefact,
                                   results=results)
        else:
            return jsonify(results)

def submit():
    tarball = request.files['tarball']
    form = request.files['form']
    secured_tarball = secure_filename(tarball.filename)
    secured_form = secure_filename(form.filename)

    # Create tmp directory to save the build request files
    tmpdir = tempfile.mkdtemp(prefix='fatbuildr', dir=current_app.config['UPLOAD_FOLDER'])
    tarball.save(os.path.join(tmpdir, secured_tarball))
    form.save(os.path.join(tmpdir, secured_form))

    # load the build request and submit to local fatbuildrd
    build_request = BuildRequest.load(tmpdir)
    connection = ClientFactory.get('local')
    build_id = connection.submit(build_request)
    return jsonify({'build': build_id})

def queue():
    connection = ClientFactory.get('local')
    running = connection.running()
    if running:
        builds = [running]
    else:
        builds = []
    builds.extend(connection.queue())
    return jsonify([vars(build) for build in builds])
