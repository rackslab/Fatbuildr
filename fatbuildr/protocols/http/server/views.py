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

import inspect
import io
from functools import wraps
import os
import tempfile
from pathlib import Path

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

from ....errors import (
    FatbuildrTokenError,
    FatbuildrServerError,
    FatbuildrServerInstanceError,
    FatbuildrServerRegistryError,
)
from ....utils import current_user
from ....version import __version__
from ...dbus.client import DBusServiceClient, DBusInstanceClient
from ....protocols.wire import WireSourceArchive, WireArtifact
from .. import (
    JsonInstance,
    JsonRunnableTask,
    JsonArtifact,
    JsonChangelogEntry,
    JsonArtifactMember,
)
from ....log import logr

logger = logr(__name__)


def error_bad_request(e):
    return render_template('error.html.j2', error="bad request (400)"), 400


def error_not_found(e):
    if request.view_args is None or (
        'output' in request.view_args and request.view_args['output'] == 'html'
    ):
        return (
            render_template('error.html.j2', error=f"{e.description} (404)"),
            404,
        )
    else:
        return jsonify(error=e.description), 404


def error_forbidden(e):
    if request.view_args is None or (
        'output' in request.view_args and request.view_args['output'] == 'html'
    ):
        return (
            render_template('error.html.j2', error=f"{e.description} (403)"),
            403,
        )
    else:
        return jsonify(error=e.description), 403


def get_token_user(instance, request):
    """Returns the user name as decoded in the token found in request
    autorization headers. Raises a HTTP/403 forbidden error if the token cannot
    be decoded properly. Returns None if the authorization header is not found,
    which is assimilated to anonymous user."""

    auth = request.headers.get('Authorization')
    if auth is None:
        return None

    if not auth.startswith('Bearer '):
        logger.warning("Malformed authorization header found in request")
        abort(403, "No valid token provided")
    token = auth.split(' ', 1)[1]
    try:
        user = current_app.token_manager(instance).decode(token)
    except FatbuildrServerInstanceError as err:
        abort(404, str(err))
    except FatbuildrTokenError as err:
        abort(403, str(err))
    return user


def check_instance_token_permission(action):
    """Decorator for Flask views functions check for valid authentification JWT
    token and permission in policy."""

    def inner_decorator(view):
        @wraps(view)
        def wrapped(instance, *args, **kwargs):
            user = get_token_user(instance, request)
            # verify unauthorized anonymous access
            if user is None and (
                not current_app.policy.allow_anonymous
                or not current_app.policy.validate_anonymous_action(action)
            ):
                logger.warning(
                    "Unauthorized anonymous access to action %s", action
                )
                abort(
                    403,
                    f"anonymous role is not allowed to perform action {action}",
                )
            # verify real user access
            elif (
                user is not None
                and not current_app.policy.validate_user_action(user, action)
            ):
                logger.warning(
                    "Unauthorized access from user %s to action %s",
                    user,
                    action,
                )
                abort(
                    403,
                    f"user {user} is not allowed to perform action "
                    f"{action}",
                )
            return view(instance, *args, **kwargs)

        return wrapped

    return inner_decorator


def get_connection(instance=None):
    """Returns the DBus client to connect to local fatbuildrd. If instance is
    None, an instance to DBusServiceClient is returned. Typically, it can be
    used to retrieve the list of defined instances. Otherwise, an instance of
    DBusInstanceClient is returned to interact with this specific instance."""
    if instance is None:
        return DBusServiceClient('dbus://system/', 'dbus')
    else:
        try:
            return DBusInstanceClient(
                f"dbus://system/{instance}", 'dbus', instance
            )
        except FatbuildrServerInstanceError:
            abort(404, f"instance {instance} not found")


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


def common_templates_variables():
    return {'version': __version__}


def fb_render_template(template, **variables):
    return render_template(
        template, **common_templates_variables(), **variables
    )


@check_instance_token_permission('view-pipeline')
def instance(instance):
    connection = get_connection(instance)
    _instance = connection.instance(instance)
    return jsonify(JsonInstance.export(_instance))


@check_instance_token_permission('view-pipeline')
def pipelines_architectures(instance):
    connection = get_connection(instance)
    return jsonify(connection.pipelines_architectures())


@check_instance_token_permission('view-pipeline')
def pipelines_formats(instance):
    connection = get_connection(instance)
    result = {}

    filter_format = request.args.get('format')
    filter_distribution = request.args.get('distribution')
    filter_environment = request.args.get('environment')
    filter_derivative = request.args.get('derivative')

    if filter_derivative:
        # May raise FatbuildrServerError if derivative is not declared in build
        # pipelines. In this case, forward as a 404.
        try:
            formats = connection.pipelines_derivative_formats(filter_derivative)
        except FatbuildrServerError as err:
            abort(404, str(err))
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
        return fb_render_template('index.html.j2', instances=instances)


def index_redirect(instance):
    return redirect(url_for('registry', instance=instance, output='html'))


@check_instance_token_permission('view-registry')
def registry(instance, output='html'):
    connection = get_connection(instance)
    formats = connection.formats()
    if output == 'json':
        return jsonify(formats)
    else:
        # add informations about tasks in HTML page
        pending = connection.queue()
        running = connection.running()
        history = connection.history(10)
        return fb_render_template(
            'registry.html.j2',
            instance=instance,
            formats=formats,
            pending=pending,
            running=running,
            history=history,
        )


@check_instance_token_permission('view-registry')
def format(instance, fmt, output='html'):
    connection = get_connection(instance)
    try:
        distributions = connection.distributions(fmt)
    except FatbuildrServerRegistryError as err:
        abort(404, str(err))
    if output == 'json':
        return jsonify(distributions)
    else:
        return fb_render_template(
            'format.html.j2',
            instance=instance,
            format=fmt,
            distributions=distributions,
        )


@check_instance_token_permission('view-registry')
def distribution(instance, fmt, distribution, output='html'):
    connection = get_connection(instance)
    try:
        derivatives = connection.derivatives(fmt, distribution)
    except FatbuildrServerRegistryError as err:
        abort(404, str(err))
    if output == 'json':
        return jsonify(derivatives)
    else:
        return fb_render_template(
            'distribution.html.j2',
            instance=instance,
            format=fmt,
            distribution=distribution,
            derivatives=derivatives,
        )


@check_instance_token_permission('view-registry')
def derivative(instance, fmt, distribution, derivative, output='html'):
    connection = get_connection(instance)
    try:
        artifacts = connection.artifacts(fmt, distribution, derivative)
    except FatbuildrServerRegistryError as err:
        abort(404, str(err))
    if output == 'json':
        return jsonify([vars(artifact) for artifact in artifacts])
    else:
        return fb_render_template(
            'derivative.html.j2',
            instance=instance,
            format=fmt,
            distribution=distribution,
            derivative=derivative,
            artifacts=artifacts,
        )


@check_instance_token_permission('view-registry')
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
    try:
        changelog = connection.changelog(
            fmt, distribution, derivative, architecture, artifact
        )
        if architecture == 'src':
            source = None
            binaries = connection.artifact_bins(
                fmt, distribution, derivative, artifact
            )
            template = 'src.html.j2'
            content = []
        else:
            source = connection.artifact_src(
                fmt, distribution, derivative, artifact
            )
            content = connection.artifact_content(
                fmt, distribution, derivative, architecture, artifact
            )
            binaries = []
            template = 'bin.html.j2'

    except FatbuildrServerRegistryError as err:
        abort(404, str(err))
    if output == 'json':
        if architecture != 'src':
            return jsonify(
                {
                    'artifact': artifact,
                    'source': JsonArtifact.export(source),
                    'changelog': [
                        JsonChangelogEntry.export(entry) for entry in changelog
                    ],
                    'content': [
                        JsonArtifactMember.export(member) for member in content
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
        return fb_render_template(
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
            content=content,
        )


@check_instance_token_permission('edit-registry')
def artifact_delete(
    instance, fmt, distribution, derivative, architecture, artifact
):
    connection = get_connection(instance)
    request_user = get_token_user(instance, request) or 'anonymous'
    _artifact = WireArtifact(
        artifact,
        architecture,
        request.args.get('version', default='-1', type=str),
    )
    # If fatbuildrweb runs with the same identity as the user submitting the
    # artifact deletion request, forward the request to fatbuildrd with a simple
    # delete_artifact() that is less restricted in polkit. Otherwise, forward
    # the request with artifact_delete_as() and the identity of the original
    # user.
    if request_user == current_user()[1]:
        task_id = connection.delete_artifact(
            fmt, distribution, derivative, _artifact
        )
    else:
        task_id = connection.delete_artifact_as(
            request_user, fmt, distribution, derivative, _artifact
        )
    return jsonify({'task': task_id})


@check_instance_token_permission('view-registry')
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
        return fb_render_template(
            'search.html.j2',
            instance=instance,
            artifact=artifact,
            results=results,
        )


@check_instance_token_permission('build')
def build(instance):
    tarball = request.files['tarball']
    # Create temporary directory with random name in fatbuildr runtime
    # directory. This directory is created manually instead of using
    # tempfile.mkdtemp() in order to avoid hard-coded mode 0700 of the latter,
    # which has the effect of setting too restricted mask in POSIX ACL that
    # prevent fatbuildrd from accessing the files.
    tarballs_dir = Path(
        current_app.config['UPLOAD_FOLDER'],
        next(tempfile._get_candidate_names()),
    )
    tarballs_dir.mkdir()
    tarball_path = tarballs_dir.joinpath(secure_filename(tarball.filename))
    tarball.save(tarball_path)

    sources = []
    for file_name in request.files.keys():
        if file_name.startswith('source/'):
            source_id = file_name[7:]
            source_archive = request.files[file_name]
            source_archive_path = tarballs_dir.joinpath(
                # The source archive filename is not secured with werkzeug
                # utility secure_filename() as the artifact main version is
                # extracted from source archive filename and it removes ~
                # (tilde) which is totally legit version numbers. As stated in
                # Flask documentation, secure_filename is notably to protect
                # from filenames with relative paths in the parents directories.
                # These kinds of filenames are cleaned up by extracting the
                # basename (without further modification).
                os.path.basename(source_archive.filename)
            )
            source_archive.save(source_archive_path)
            sources.append(WireSourceArchive(source_id, source_archive_path))

    connection = get_connection(instance)
    request_user = get_token_user(instance, request) or 'anonymous'

    # If fatbuildrweb runs with the same identity as the user submitting the
    # build request, forward the request to fatbuildrd with a simple build()
    # that is less restricted in polkit. Otherwise, forward the request with
    # build_as() and the identity of the original user.
    if request_user == current_user()[1]:
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
            sources,
            False,
        )
    else:
        task_id = connection.build_as(
            request_user,
            request.form['format'],
            request.form['distribution'],
            request.form['architectures'].split(','),
            request.form['derivative'],
            request.form['artifact'],
            request.form['user_name'],
            request.form['user_email'],
            request.form['message'],
            tarball_path,
            sources,
            False,
        )
    return jsonify({'task': task_id})


@check_instance_token_permission('view-task')
def running(instance):
    connection = get_connection(instance)
    running = connection.running()
    if running:
        return jsonify(JsonRunnableTask.export(running))
    return jsonify(None)


@check_instance_token_permission('view-task')
def queue(instance):
    connection = get_connection(instance)
    tasks = connection.queue()
    return jsonify([JsonRunnableTask.export(task) for task in tasks])


@check_instance_token_permission('view-task')
def task(instance, task_id):
    connection = get_connection(instance)
    try:
        task = connection.get(task_id)
    except FatbuildrServerError as err:
        abort(404, str(err))
    return jsonify(JsonRunnableTask.export(task))


@check_instance_token_permission('view-task')
def watch(instance, task_id, output='html'):
    """Stream lines obtained by DBusInstanceClient.watch() generator."""
    connection = get_connection(instance)
    try:
        task = connection.get(task_id)
    except FatbuildrServerError as err:
        abort(404, str(err))

    # X-Accel-Buffering is disabled in response header to avoid potential
    # reverse proxies between clients and fatbuildrweb for buffering the tasks
    # output which would cause boring latencies.
    if output == 'html':
        return current_app.response_class(
            stream_with_context(
                stream_template(
                    'watch.html.j2',
                    instance=instance,
                    task=task_id,
                    messages=connection.watch(task),
                )
            ),
            headers={'X-Accel-Buffering': 'no'},
        )
    else:
        return current_app.response_class(
            connection.watch(task, binary=True),
            mimetype='application/octet-stream',
            headers={'X-Accel-Buffering': 'no'},
        )


@check_instance_token_permission('view-keyring')
def keyring(instance):
    connection = get_connection(instance)
    keyring = connection.keyring_export()
    if keyring is None:
        abort(404, 'No keyring available on this instance')
    mem = io.BytesIO()
    mem.write(keyring.encode())
    mem.seek(0)
    filename = 'keyring.asc'
    # Starting with Flask >= 2.0, send_file attachment_filename argument has
    # been renamed download_name. Fatbuildr has the goal to support systems with
    # Flask < 2.0 then logic is implemented to support both interfaces.
    if 'download_name' in inspect.getfullargspec(send_file).args:
        kwargs = {'download_name': filename}
    else:
        kwargs = {'attachment_filename': filename}
    return send_file(
        mem,
        as_attachment=True,
        mimetype='text/plain',
        **kwargs,
    )


def content(instance, filename):
    instance_registry_folder = current_app.config['REGISTRY_FOLDER'].joinpath(
        instance
    )
    path = instance_registry_folder.joinpath(filename)
    if not path.exists():
        abort(404, 'File not found in registry')
    if path.is_dir():
        if current_app.conf.run.listing:
            return fb_render_template(
                'dir.html.j2',
                instance=instance,
                instance_registry_folder=instance_registry_folder,
                path=path,
            )
        else:
            abort(403, 'Access forbidden')
    else:
        mimetype = None

        # Hack for Red Hat Satellite (Pulp/aiohttp).
        #
        # For compressed XML files, Flask set response headers to these values:
        #
        # content-encoding: gzip
        # content-type: application/xml; charset=utf-8
        #
        # The aiohttp library automatically decompress response content for its
        # consumer application (ie. Pulp or Red Hat Satellite) when
        # 'content-encoding: gzip' is set in response headers. This makes Red
        # Hat Satellite and Pulp fail because of unmatching checksums between
        # the downloaded files and repository metadata eventually. For
        # reference, this behavior is discussed here:
        # https://github.com/pulp/pulp-smash/issues/1309
        #
        # A simple workaround for this is to force mimetype to application/gzip.
        # This way, Flask does not set content-encoding header in its response,
        # and Pulp get the raw compressed file and can validate checksums
        # eventually.
        if filename.endswith('.xml.gz'):
            mimetype = "application/gzip"

        return send_from_directory(
            current_app.config['REGISTRY_FOLDER'].joinpath(instance),
            filename,
            mimetype=mimetype,
        )
