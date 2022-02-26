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

import argparse
import sys
import os
import time
from pathlib import Path
import tempfile
import tarfile
from datetime import datetime

from . import FatbuildrCliRun
from ..version import __version__
from ..conf import RuntimeConfCtl
from ..prefs import UserPreferences
from ..images import ImagesManager
from ..log import logr
from ..protocols import ClientFactory
from ..protocols.crawler import register_protocols
from ..artefact import ArtefactDefs

logger = logr(__name__)


def progname():
    """Return the name of the program."""
    return os.path.basename(sys.argv[0])


def default_user_pref():
    """Returns the default path to the user preferences file, through
    XDG_CONFIG_HOME environment variable if it is set."""
    ini = 'fatbuildr.ini'
    xdg_env = os.getenv('XDG_CONFIG_HOME')
    if xdg_env:
        return Path(xdg_env).join(ini)
    else:
        return Path(f"~/.config/{ini}")


def prepare_tarball(basedir, subdir):
    # create tmp submission directory
    tarball = Path(tempfile._get_default_tempdir()).joinpath(
        f"fatbuildr-artefact-{next(tempfile._get_candidate_names())}.tar.xz"
    )

    artefact_def_path = Path(basedir, subdir)
    if not artefact_def_path.exists():
        raise RuntimeError(
            f"artefact definition directory {artefact_def_path} does not "
            "exist",
        )

    logger.debug(
        "Creating archive %s with artefact definition directory %s",
        tarball,
        artefact_def_path,
    )
    tar = tarfile.open(tarball, 'x:xz')
    tar.add(artefact_def_path, arcname='.', recursive=True)
    tar.close()

    return tarball


class Fatbuildrctl(FatbuildrCliRun):
    def __init__(self):
        super().__init__()

        parser = argparse.ArgumentParser(
            description='Do something with fatbuildr.'
        )
        parser.add_argument(
            '-v',
            '--version',
            dest='version',
            action='version',
            version='%(prog)s ' + __version__,
        )
        parser.add_argument(
            '--debug',
            dest='debug',
            action='store_true',
            help="Enable debug mode",
        )
        parser.add_argument(
            '--fulldebug',
            action='store_true',
            help="Enable debug mode in external libs",
        )
        parser.add_argument(
            '-i', '--instance', dest='instance', help="Name of the instance"
        )
        parser.add_argument(
            '--preferences',
            help="Path to user preference file (default: %(default)s)",
            type=Path,
            default=default_user_pref(),
        )
        parser.add_argument(
            '--host', dest='host', help="Fatbuildr host", default='local'
        )

        subparsers = parser.add_subparsers(
            help='Action to perform', dest='action', required=True
        )

        # Parser for the images command
        parser_images = subparsers.add_parser(
            'images', help='Manage build images'
        )
        parser_images.add_argument(
            '--create', action='store_true', help='Create the images'
        )
        parser_images.add_argument(
            '--update', action='store_true', help='Update the images'
        )
        parser_images.add_argument(
            '--format',
            help='Manage image and build environment for this format',
        )
        parser_images.add_argument(
            '--force',
            action='store_true',
            help='Force creation of images even they already exist',
        )
        parser_images.add_argument(
            '--create-envs',
            action='store_true',
            help='Create the build environments in the images',
        )
        parser_images.add_argument(
            '--update-envs',
            action='store_true',
            help='Update the build environments in the images',
        )
        parser_images.set_defaults(func=self._run_images)

        # Parser for the keyring command
        parser_keyring = subparsers.add_parser(
            'keyring', help='Manage signing keyring'
        )
        parser_keyring.add_argument(
            '--create', action='store_true', help='Create keyring'
        )
        parser_keyring.add_argument(
            '--show', action='store_true', help='Show keyring information'
        )
        parser_keyring.add_argument(
            '--export', action='store_true', help='Export keyring'
        )
        parser_keyring.set_defaults(func=self._run_keyring)

        # Parser for the build command
        parser_build = subparsers.add_parser('build', help='Submit new build')
        parser_build.add_argument(
            '-a', '--artefact', help='Artefact name', required=True
        )
        parser_build.add_argument(
            '-d', '--distribution', help='Distribution name'
        )
        parser_build.add_argument(
            '-f', '--format', help='Format of the artefact'
        )
        parser_build.add_argument(
            '--derivative',
            help='Distribution derivative',
            default='main',
        )
        parser_build.add_argument(
            '-b',
            '--basedir',
            help='Artefacts definitions directory',
        )
        parser_build.add_argument(
            '-s', '--subdir', help='Artefact subdirectory'
        )
        parser_build.add_argument('-n', '--name', help='Maintainer name')
        parser_build.add_argument('-e', '--email', help='Maintainer email')
        parser_build.add_argument('-m', '--msg', help='Build log message')
        parser_build.add_argument(
            '-w',
            '--watch',
            action='store_true',
            help='Watch build log and wait until its end',
        )
        parser_build.set_defaults(func=self._run_build)

        # Parser for the list command
        parser_list = subparsers.add_parser('list', help='List builds')
        parser_list.set_defaults(func=self._run_list)

        # Parser for the watch command
        parser_watch = subparsers.add_parser('watch', help='Watch build')
        parser_watch.add_argument('-b', '--build', help='ID of build to watch')
        parser_watch.set_defaults(func=self._run_watch)

        # Parser for the archives command
        parser_archives = subparsers.add_parser(
            'archives', help='List archives'
        )
        parser_archives.set_defaults(func=self._run_archives)

        # Parser for the registry command
        parser_registry = subparsers.add_parser(
            'registry', help='Manage artefact registries'
        )
        parser_registry.add_argument(
            'operation',
            help='Operation on selected artefacts (default: %(default)s)',
            nargs='?',
            choices=['list', 'delete'],
            default='list',
        )
        parser_registry.add_argument(
            '-d', '--distribution', help='Distribution name', required=True
        )
        parser_registry.add_argument(
            '--derivative', help='Distribution derivative', default='main'
        )
        parser_registry.add_argument(
            '-a', '--artefact', help='Name of artefact'
        )

        parser_registry.set_defaults(func=self._run_registry)

        args = parser.parse_args()

        logger.setup(args.debug or args.fulldebug, args.fulldebug)
        self.conf = RuntimeConfCtl()
        self.load(args)

        # run the method corresponding to the provided action
        args.func(args)

    def load(self, args):
        """Load main configuration file and user preferences, then set common
        parameters accordingly."""

        # Load main configuration
        super().load()

        # load all tasks and exportable types structures in protocol
        register_protocols()

        # Load user preferences
        self.prefs = UserPreferences(args.preferences)

        # Set host with args, prefs, 'local' descending priority
        if args.host is None:
            if self.prefs.host is None:
                self.host = 'local'
            else:
                self.host = self.prefs.host
        else:
            self.host = args.host

        # Set instance with args, prefs, 'default', descending priority
        if args.instance is None:
            if self.prefs.instance is None:
                self.instance = 'default'
            else:
                self.instance = self.prefs.instance
        else:
            self.instance = args.instance

        self.prefs.dump()

    def _run_images(self, args):
        logger.debug("running images task")
        connection = ClientFactory.get(self.host)

        mgr = ImagesManager(self.conf, self.instance)
        if args.format:
            selected_formats = [args.format]
        else:
            selected_formats = connection.pipelines_formats(self.instance)
        logger.debug("Selected formats: %s", selected_formats)

        # check if operation is on images and run it
        if args.create:
            for format in selected_formats:
                task_id = connection.image_create(
                    self.instance, format, args.force
                )
                print(f"Submitted {format} image creation task {task_id}")
            return
        elif args.update:
            for format in selected_formats:
                task_id = connection.image_update(self.instance, format)
                print(f"Submitted {format} image update task {task_id}")
            return
        else:
            print(
                "An operation on the images must be specified, type "
                f"'{progname()} images --help' for details"
            )
            sys.exit(1)

        # At this stage, the operation is on build environments

        for format in selected_formats:

            distributions = connection.pipelines_format_distributions(
                self.instance, format
            )
            if not distributions:
                logger.info("No distribution defined for %s image", format)
            envs = []
            for distribution in distributions:
                env = connection.pipelines_distribution_environment(
                    self.instance, distribution
                )
                if env is not None:
                    envs.append(env)
            logger.debug(
                "Build environments found for format %s: %s", format, envs
            )

            if args.create_envs:
                mgr.create_envs(format, envs)
            elif args.update_envs:
                mgr.update_envs(format, envs)

    def _run_keyring(self, args):
        logger.debug("running keyring operation")
        connection = ClientFactory.get(self.host)
        if args.create:
            task_id = connection.keyring_create(self.instance)
            print(f"Submitted keyring creation task {task_id}")
        elif args.show:
            keyring = connection.keyring(self.instance)
            keyring.report()
        elif args.export:
            print(connection.keyring_export(self.instance), end='')
        else:
            print(
                "An operation on the keyring must be specified, type "
                f"'{progname()} keyring --help' for details"
            )
            sys.exit(1)

    def _run_build(self, args):
        logger.debug(
            "running build for artefact: %s instance: %s"
            % (args.artefact, self.instance)
        )

        connection = ClientFactory.get(self.host)

        # Set basedir with args, prefs descending priority, or fail
        if args.basedir is None:
            if self.prefs.basedir is None:
                print(
                    "Base directory must be defined for build operations, "
                    "either with --basedir argument or through user "
                    "preferences file."
                )
                sys.exit(1)
            else:
                basedir = self.prefs.basedir
        else:
            basedir = args.basedir

        # Set user name with args, prefs descending priority, or fail
        if args.name is None:
            if self.prefs.user_name is None:
                print(
                    "The user name be defined for build operations, "
                    "either with --name argument or through user "
                    "preferences file."
                )
                sys.exit(1)
            else:
                user_name = self.prefs.user_name
        else:
            user_name = args.name

        # Set user email with args, prefs descending priority, or fail
        if args.email is None:
            if self.prefs.user_email is None:
                print(
                    "The user email must be defined for build operations, "
                    "either with --email argument or through user "
                    "preferences file."
                )
                sys.exit(1)
            else:
                user_email = self.prefs.user_email
        else:
            user_email = args.email

        # Set build_msg with args, prefs descending priority, or fail
        if args.msg is None:
            if self.prefs.message is None:
                print(
                    "The build message must be defined for build operations, "
                    "either with --msg argument or through user "
                    "preferences file."
                )
                sys.exit(1)
            else:
                build_msg = self.prefs.message
        else:
            build_msg = args.msg

        # Set subdir, which defaults to artefact name
        if args.subdir is None:
            subdir = args.artefact
        else:
            subdir = args.subdir

        defs = ArtefactDefs(Path(basedir, subdir))

        format = None
        distribution = None

        if args.distribution:
            distribution = args.distribution
            dist_fmt = connection.pipelines_distribution_format(
                self.instance, args.distribution
            )
            # if format is also given, check it matches
            if args.format and args.format != dist_fmt:
                logger.error(
                    "Specified format %s does not match the format "
                    "of the specified distribution %s",
                    args.format,
                    args.distribution,
                )
                sys.exit(1)
            format = dist_fmt
        elif args.format is None:
            # distribution and format have not been specified, check format
            # supported by the artefact.
            supported_fmts = defs.supported_formats
            # check if there is not more than one supported format for this
            # artefact
            if len(supported_fmts) > 1:
                logger.error(
                    "There is more than one supported format for "
                    "artefact %s, at least the format must be "
                    "specified" % (args.artefact)
                )
                sys.exit(1)
            if supported_fmts:
                format = supported_fmts[0]
                logger.debug(
                    "Format %s has been selected for artefact %s"
                    % (format, args.artefact)
                )

        if not format:
            logger.error(
                "Unable to define format of artefact %s, either the "
                "distribution or the format must be specified" % (args.artefact)
            )
            sys.exit(1)
        elif not args.distribution:
            format_dists = connection.pipelines_format_distributions(
                self.instance, format
            )
            # check if there is not more than one distribution for this format
            if len(format_dists) > 1:
                logger.error(
                    "There is more than one distribution for the "
                    "format %s in pipelines definition, the "
                    "distribution must be specified" % (format)
                )
                sys.exit(1)
            distribution = format_dists[0]
            logger.debug(
                "Distribution %s has been selected for format %s"
                % (distribution, format)
            )

        # check artefact accepts this format
        if format not in defs.supported_formats:
            logger.error(
                "Format %s is not accepted by artefact %s",
                format,
                args.artefact,
            )
            sys.exit(1)

        # check artefact accepts this derivative
        if args.derivative not in defs.derivatives:
            logger.error(
                "Derivative %s is not accepted by artefact %s",
                args.derivative,
                args.artefact,
            )
            sys.exit(1)

        # check format is accepted for this derivative
        if format not in connection.pipelines_derivative_formats(
            self.instance, args.derivative
        ):
            logger.error(
                "Derivative %s does not accept format %s",
                args.derivative,
                format,
            )
            sys.exit(1)

        try:
            tarball = prepare_tarball(basedir, subdir)
            build_id = connection.submit(
                self.instance,
                format,
                distribution,
                args.derivative,
                args.artefact,
                user_name,
                user_email,
                build_msg,
                tarball,
            )
        except RuntimeError as err:
            logger.error("Error while submitting build: %s" % (err))
            sys.exit(1)
        logger.info("Build %s submitted" % (build_id))
        if args.watch:
            self._watch_build(build_id)

    def _run_list(self, args):
        logger.debug("running list")
        connection = ClientFactory.get(self.host)
        try:
            _running = connection.running(self.instance)
            if _running:
                print("Running build:")
                _running.report()
            else:
                print("No running build")

            _queue = connection.queue(self.instance)
            if _queue:
                print("Pending build submissions:")
                for _build in _queue:
                    _build.report()

        except RuntimeError as err:
            logger.error("Error while listing builds: %s" % (err))
            sys.exit(1)

    def _watch_build(self, build_id):
        connection = ClientFactory.get(self.host)
        try:
            build = connection.get(self.instance, build_id)
        except RuntimeError as err:
            logger.error(err)
            sys.exit(1)

        warned_pending = False
        # if build is pending, wait
        while build.state == 'pending':
            if not warned_pending:
                logger.info(
                    "Build %s is pending, waiting for the build to start."
                    % (build.id)
                )
                warned_pending = True
            time.sleep(1)
            # poll build state again
            build = connection.get(self.instance, build_id)
        try:
            for line in connection.watch(self.instance, build):
                print(line, end='')
        except KeyboardInterrupt:
            # Leave gracefully after a keyboard interrupt (eg. ^c)
            logger.debug("Received keyboard interrupt, leaving.")
        except BrokenPipeError:
            # Stop if hit a broken pipe. It could happen when watch is given to
            # `head` for example.
            pass

    def _run_watch(self, args):
        self._watch_build(args.build)

    def _run_archives(self, args):
        connection = ClientFactory.get(self.host)
        archives = connection.archives(self.instance)
        if not archives:
            print("No archive found")
            return
        print("Build archives:")
        for archive in archives:
            archive.report()

    def _run_registry(self, args):
        connection = ClientFactory.get(self.host)
        _fmt = connection.pipelines_distribution_format(
            self.instance, args.distribution
        )
        artefacts = connection.artefacts(
            self.instance, _fmt, args.distribution, args.derivative
        )
        if args.artefact:
            # filter out other artefact names
            artefacts = [
                artefact
                for artefact in artefacts
                if args.artefact in artefact.name
            ]
        if not artefacts:
            print(
                f"No artefact found in {_fmt} distribution {args.distribution} "
                f"derivative {args.derivative}"
            )
            return
        if args.operation == 'list':
            print(
                f"Artefacts found for {_fmt} distribution {args.distribution} "
                f"derivative {args.derivative}:"
            )
            for artefact in artefacts:
                artefact.report()
        elif args.operation == 'delete':
            for artefact in artefacts:
                task_id = connection.delete_artefact(
                    self.instance,
                    _fmt,
                    args.distribution,
                    args.derivative,
                    artefact,
                )
                print(
                    f"Submitted artefact {artefact.name} deletion task {task_id}"
                )
