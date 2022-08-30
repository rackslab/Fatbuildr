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

import io

from flask import (
    request,
    jsonify,
    render_template,
    current_app,
    send_from_directory,
    send_file,
    stream_with_context,
    abort,
    Response,
    url_for,
    redirect,
)
from werkzeug.utils import secure_filename

from ..version import __version__
from ..protocols import ClientFactory
from ..protocols.http import (
    JsonInstance,
    JsonRunnableTask,
    JsonArtifact,
    JsonChangelogEntry,
)


def error_bad_request(e):
    return render_template('error.html.j2', error="bad request (400)"), 400


def get_connection(instance='default'):
    return ClientFactory.get('dbus://system/' + instance)


def stream_template(template_name, **context):
    """Utility to stream content using template, as explained in Flask
    documentation:
    https://flask.palletsprojects.com/en/2.1.x/patterns/streaming/"""
    current_app.update_template_context(context)
    t = current_app.jinja_env.get_template(template_name)
    rv = t.stream(context)
    rv.enable_buffering(5)
    return rv


def version():
    return Response(f"Fatbuildr v{__version__}", mimetype='text/plain')


def instance(instance):
    connection = get_connection(instance)
    _instance = connection.instance(instance)
    return jsonify(JsonInstance.export(_instance))


def pipelines_architectures(instance):
    connection = get_connection(instance)
    return jsonify(connection.pipelines_architectures())


def pipelines_formats(instance):
    connection = get_connection(instance)
    result = {}

    filter_format = request.args.get('format')
    filter_distribution = request.args.get('distribution')
    filter_environment = request.args.get('environment')
    filter_derivative = request.args.get('derivative')

    if filter_derivative:
        formats = connection.pipelines_derivative_formats(filter_derivative)
    else:
        formats = connection.pipelines_formats()
    for format in formats:
        if filter_format and format != filter_format:
            continue
        distributions = connection.pipelines_format_distributions(format)
        for distribution in distributions:
            if filter_distribution and distribution != filter_distribution:
                continue
            environment = connection.pipelines_distribution_environment(
                distribution
            )
            if filter_environment and environment != filter_environment:
                continue
            derivatives = connection.pipelines_distribution_derivatives(
                distribution
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
    connection = get_connection()
    instances = connection.instances()
    if output == 'json':
        return jsonify(
            [JsonInstance.export(instance) for instance in instances]
        )
    else:
        return render_template('index.html.j2', instances=instances)


def index_redirect(instance):
    redirect(url_for('registry', instance=instance, output='html'))


def registry(instance, output='html'):
    connection = get_connection(instance)
    formats = connection.formats()
    if output == 'json':
        return jsonify(formats)
    else:
        # add informations about tasks in HTML page
        pending = connection.queue()
        running = connection.running()
        archives = connection.archives(10)
        return render_template(
            'registry.html.j2',
            instance=instance,
            formats=formats,
            pending=pending,
            running=running,
            archives=archives,
        )


def format(instance, fmt, output='html'):
    connection = get_connection(instance)
    distributions = connection.distributions(fmt)
    if output == 'json':
        return jsonify(distributions)
    else:
        return render_template(
            'format.html.j2',
            instance=instance,
            format=fmt,
            distributions=distributions,
        )


def distribution(instance, fmt, distribution, output='html'):
    connection = get_connection(instance)
    derivatives = connection.derivatives(fmt, distribution)
    if output == 'json':
        return jsonify(derivatives)
    else:
        return render_template(
            'distribution.html.j2',
            instance=instance,
            format=fmt,
            distribution=distribution,
            derivatives=derivatives,
        )


def derivative(instance, fmt, distribution, derivative, output='html'):
    connection = get_connection(instance)
    artifacts = connection.artifacts(fmt, distribution, derivative)
    if output == 'json':
        return jsonify([vars(artifact) for artifact in artifacts])
    else:
        return render_template(
            'derivative.html.j2',
            instance=instance,
            format=fmt,
            distribution=distribution,
            derivative=derivative,
            artifacts=artifacts,
        )


def artifact(
    instance,
    fmt,
    distribution,
    derivative,
    architecture,
    artifact,
    output='html',
):
    connection = get_connection(instance)
    if architecture == 'src':
        source = None
        binaries = connection.artifact_bins(
            fmt, distribution, derivative, artifact
        )
        template = 'src.html.j2'
    else:
        source = connection.artifact_src(
            fmt, distribution, derivative, artifact
        )
        binaries = []
        template = 'bin.html.j2'
    changelog = connection.changelog(
        fmt, distribution, derivative, architecture, artifact
    )

    if output == 'json':
        if architecture != 'src':
            return jsonify(
                {
                    'artifact': artifact,
                    'source': JsonArtifact.export(source),
                    'changelog': [
                        JsonChangelogEntry.export(entry) for entry in changelog
                    ],
                }
            )
        else:
            return jsonify(
                {
                    'artifact': artifact,
                    'binaries': [
                        JsonArtifact.export(binary) for binary in binaries
                    ],
                    'changelog': [
                        JsonChangelogEntry.export(entry) for entry in changelog
                    ],
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
            artifact=artifact,
            source=source,
            binaries=binaries,
            changelog=changelog,
        )


def search(instance, output='html'):
    connection = get_connection(instance)
    formats = connection.formats()
    results = {}

    artifact = request.args.get('artifact')

    if not artifact:
        abort(400)

    for fmt in formats:
        distributions = connection.distributions(fmt)
        for distribution in distributions:
            derivatives = connection.derivatives(fmt, distribution)
            for derivative in derivatives:
                artifacts = connection.artifacts(fmt, distribution, derivative)
                for _artifact in artifacts:
                    if artifact in _artifact.name:
                        if fmt not in results:
                            results[fmt] = {}
                        if distribution not in results[fmt]:
                            results[fmt][distribution] = {}
                        if derivative not in results[fmt][distribution]:
                            results[fmt][distribution][derivative] = []
                        results[fmt][distribution][derivative].append(_artifact)

    if output == 'json':
        # Convert lists of WireArtifact into lists of dicts for JSON
        # serialization
        for fmt, distributions in results.items():
            for distribution, derivatives in distributions.items():
                for derivative, artifacts in derivatives.items():
                    results[fmt][distribution][derivative] = [
                        JsonArtifact.export(_artifact)
                        for _artifact in artifacts
                    ]
        return jsonify(results)
    else:
        return render_template(
            'search.html.j2',
            instance=instance,
            artifact=artifact,
            results=results,
        )


def build(instance):
    tarball = request.files['tarball']
    tarball_path = current_app.config['UPLOAD_FOLDER'].joinpath(
        secure_filename(tarball.filename)
    )
    tarball.save(tarball_path)

    src_tarball_path = None
    if 'source' in request.files:
        src_tarball = request.files['source']
        src_tarball_path = current_app.config['UPLOAD_FOLDER'].joinpath(
            secure_filename(src_tarball.filename)
        )
        src_tarball.save(src_tarball_path)

    connection = get_connection(instance)
    task_id = connection.build(
        request.form['format'],
        request.form['distribution'],
        request.form['architectures'].split(','),
        request.form['derivative'],
        request.form['artifact'],
        request.form['user_name'],
        request.form['user_email'],
        request.form['message'],
        tarball_path,
        src_tarball_path,
        False,
    )
    return jsonify({'task': task_id})


def running(instance):
    connection = get_connection(instance)
    running = connection.running()
    if running:
        return jsonify(JsonRunnableTask.export(running))
    return jsonify(None)


def queue(instance):
    connection = get_connection(instance)
    tasks = connection.queue()
    return jsonify([JsonRunnableTask.export(task) for task in tasks])


def task(instance, task_id):
    connection = get_connection(instance)
    task = connection.get(task_id)
    return jsonify(JsonRunnableTask.export(task))


def watch(instance, task_id, output='html'):
    """Stream lines obtained by DBusClient.watch() generator."""
    connection = get_connection(instance)
    task = connection.get(task_id)
    if output == 'html':
        return current_app.response_class(
            stream_with_context(
                stream_template(
                    'watch.html.j2',
                    instance=instance,
                    task=task_id,
                    messages=connection.watch(task),
                )
            )
        )
    else:
        return current_app.response_class(
            connection.watch(task, binary=True),
            mimetype='application/octet-stream',
        )


def keyring(instance):
    connection = get_connection(instance)
    mem = io.BytesIO()
    mem.write(connection.keyring_export().encode())
    mem.seek(0)
    return send_file(
        mem,
        as_attachment=True,
        attachment_filename='keyring.asc',
        mimetype='text/plain',
    )


def content(instance, filename):
    return send_from_directory(
        current_app.config['REGISTRY_FOLDER'].joinpath(instance),
        filename,
    )
