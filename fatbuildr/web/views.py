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
import io

from flask import (
    request,
    jsonify,
    render_template,
    current_app,
    send_from_directory,
    send_file,
)
from werkzeug.utils import secure_filename

from ..version import __version__
from ..protocols import ClientFactory
from ..builds import BuildRequest


def version():
    return f"Fatbuildr v{__version__}"


def instance(instance):
    connection = ClientFactory.get('local')
    _instance = connection.instance(instance)
    return jsonify(_instance.to_dict())


def pipelines_formats(instance):
    connection = ClientFactory.get('local')
    result = {}

    filter_format = request.args.get('format')
    filter_distribution = request.args.get('distribution')
    filter_environment = request.args.get('environment')

    formats = connection.pipelines_formats(instance)
    for format in formats:
        if filter_format and format != filter_format:
            continue
        distributions = connection.pipelines_format_distributions(
            instance, format
        )
        for distribution in distributions:
            if filter_distribution and distribution != filter_distribution:
                continue
            environment = connection.pipelines_distribution_environment(
                instance, distribution
            )
            if filter_environment and environment != filter_environment:
                continue
            derivatives = connection.pipelines_distribution_derivatives(
                instance, distribution
            )
            if format not in result:
                result[format] = []
            result[format].append(
                {
                    'distribution': distribution,
                    'environment': environment,
                    'derivatives': derivatives,
                }
            )
    return jsonify(result)


def index(output='html'):
    connection = ClientFactory.get('local')
    instances = connection.registry_instances()
    if output == 'json':
        return jsonify(instances)
    else:
        return render_template('index.html.j2', instances=instances)


def registry_formats(instance, output='html'):
    connection = ClientFactory.get('local')
    formats = connection.formats(instance)
    if output == 'json':
        return jsonify(formats)
    else:
        return render_template(
            'instance.html.j2', instance=instance, formats=formats
        )


def format_distributions(instance, fmt, output='html'):
    connection = ClientFactory.get('local')
    distributions = connection.distributions(instance, fmt)
    if output == 'json':
        return jsonify(distributions)
    else:
        return render_template(
            'format.html.j2',
            instance=instance,
            format=fmt,
            distributions=distributions,
        )


def distribution_derivatives(instance, fmt, distribution, output='html'):
    connection = ClientFactory.get('local')
    derivatives = connection.derivatives(instance, fmt, distribution)
    if output == 'json':
        return jsonify(derivatives)
    else:
        return render_template(
            'distribution.html.j2',
            instance=instance,
            format=fmt,
            distribution=distribution,
            derivatives=derivatives,
            artefacts=artefacts,
        )


def derivative_artefacts(
    instance, fmt, distribution, derivative, output='html'
):
    connection = ClientFactory.get('local')
    artefacts = connection.artefacts(instance, fmt, distribution, derivative)
    if output == 'json':
        return jsonify([vars(artefact) for artefact in artefacts])
    else:
        return render_template(
            'derivative.html.j2',
            instance=instance,
            format=fmt,
            distribution=distribution,
            derivative=derivative,
            artefacts=artefacts,
        )


def artefact(
    instance,
    fmt,
    distribution,
    derivative,
    architecture,
    artefact,
    output='html',
):
    connection = ClientFactory.get('local')
    if architecture == 'src':
        source = None
        binaries = connection.artefact_bins(
            instance, fmt, distribution, derivative, artefact
        )
        template = 'src.html.j2'
    else:
        source = connection.artefact_src(
            instance, fmt, distribution, derivative, artefact
        )
        binaries = []
        template = 'bin.html.j2'
    changelog = connection.changelog(
        instance, fmt, distribution, derivative, architecture, artefact
    )

    if output == 'json':
        if source:
            return jsonify(
                {
                    'artefact': artefact,
                    'source': source.to_dict(),
                    'changelog': [entry.to_dict() for entry in changelog],
                }
            )
        else:
            return jsonify(
                {
                    'artefact': artefact,
                    'binaries': [binary.to_dict() for binary in binaries],
                    'changelog': [entry.to_dict() for entry in changelog],
                }
            )
    else:
        return render_template(
            template,
            instance=instance,
            format=fmt,
            distribution=distribution,
            derivative=derivative,
            architecture=architecture,
            artefact=artefact,
            source=source,
            binaries=binaries,
            changelog=changelog,
        )


def artefacts(instance, artefact, output='html'):
    connection = ClientFactory.get('local')
    formats = connection.formats(instance)
    results = {}

    for fmt in formats:
        distributions = connection.distributions(instance, fmt)
        for distribution in distributions:
            derivatives = connection.derivatives(instance, fmt, distribution)
            for derivative in derivatives:
                artefacts = connection.artefacts(
                    instance, fmt, distribution, derivative
                )
                for _artefact in artefacts:
                    if artefact == _artefact.name:
                        if fmt not in results:
                            results[fmt] = {}
                        if distribution not in results[fmt]:
                            results[fmt][distribution] = {}
                        if derivative not in results[fmt][distribution]:
                            results[fmt][distribution][derivative] = []
                        results[fmt][distribution][derivative].append(_artefact)

    if output == 'json':
        # Convert lists of WireArtefact into lists of dicts for JSON
        # serialization
        for fmt, distributions in results.items():
            for distribution, derivatives in distributions.items():
                for derivative, artefacts in derivatives.items():
                    results[fmt][distribution][derivative] = [
                        _artefact.to_dict() for artefact in artefacts
                    ]
        return jsonify(results)
    else:
        return render_template(
            'artefacts.html.j2',
            instance=instance,
            artefact=artefact,
            results=results,
        )


def submit():
    tarball = request.files['tarball']
    form = request.files['form']
    secured_tarball = secure_filename(tarball.filename)
    secured_form = secure_filename(form.filename)

    # Create tmp directory to save the build request files
    tmpdir = tempfile.mkdtemp(
        prefix='fatbuildr', dir=current_app.config['UPLOAD_FOLDER']
    )
    tarball.save(os.path.join(tmpdir, secured_tarball))
    form.save(os.path.join(tmpdir, secured_form))

    # load the build request and submit to local fatbuildrd
    build_request = BuildRequest.load(tmpdir)
    connection = ClientFactory.get('local')
    build_id = connection.submit(build_request)
    return jsonify({'build': build_id})


def running():
    connection = ClientFactory.get('local')
    running = connection.running()
    if running:
        return jsonify(running.to_dict())
    return jsonify(None)


def queue():
    connection = ClientFactory.get('local')
    builds = connection.queue()
    return jsonify([build.to_dict() for build in builds])


def build(build_id):
    connection = ClientFactory.get('local')
    build = connection.get(build_id)
    return jsonify(build.to_dict())


def watch(build_id):
    """Stream lines obtained by DbusClient.watch() generator."""
    connection = ClientFactory.get('local')
    build = connection.get(build_id)
    return current_app.response_class(
        connection.watch(build), mimetype='text/plain'
    )


def keyring(instance):
    connection = ClientFactory.get('local')
    mem = io.BytesIO()
    mem.write(connection.keyring_export(instance).encode())
    mem.seek(0)
    return send_file(
        mem,
        as_attachment=True,
        attachment_filename='keyring.asc',
        mimetype='text/plain',
    )


def content(instance, filename):
    return send_from_directory(
        os.path.join(current_app.config['REGISTRY_FOLDER'], instance),
        filename,
    )
