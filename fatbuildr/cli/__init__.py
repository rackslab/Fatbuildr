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
import logging
import atexit
import time

from ..version import __version__
from ..conf import RuntimeConfd, RuntimeConfCtl
from ..images import ImagesManager
from ..keyring import KeyringManager
from ..builds.manager import BuildsManager
from ..builds.factory import BuildFactory
from ..cleanup import CleanupRegistry

logger = logging.getLogger(__name__)


def progname():
    """Return the name of the program."""
    return os.path.basename(sys.argv[0])


class FatbuildrCliRun(object):

    @classmethod
    def run(cls):
        """Instanciate and execute the CliRun."""
        atexit.register(CleanupRegistry.clean)
        run = cls()

    def __init__(self):

        self.conf = None

    def load(self):

        try:
            self.conf.load()  # load configuration file
        except ValueError as err:
            logger.error("Error while loading configuration: %s" % (err))
            sys.exit(1)


class Fatbuildrd(FatbuildrCliRun):

    def __init__(self):
        super().__init__()

        parser = argparse.ArgumentParser(description='Do something with fatbuildr.')
        parser.add_argument('-v', '--version', dest='version', action='version', version='%(prog)s ' + __version__)
        parser.add_argument('--debug', dest='debug', action='store_true', help="Enable debug mode")

        args = parser.parse_args()

        # setup logger according to args
        if args.debug:
            logging_level = logging.DEBUG
        else:
            logging_level = logging.INFO
        logging.basicConfig(level=logging_level)

        self.conf = RuntimeConfd()
        self.load()
        self._run()

    def load(self):
        super().load()

        # set debug level on root logger if set in conf file
        if self.conf.run.debug:
            logging.getLogger().setLevel(level=logging.DEBUG)

        self.conf.dump()

    def _run(self):
        logger.debug("Running fatbuildrd")
        mgr = BuildsManager(self.conf)

        while not mgr.empty:
            try:
                # pick the first request in queue
                request = mgr.pick()
                logger.info("Processing build %s" % (request.id))
                # set the request instance in the runtime conf
                self.conf.run.instance = request.instance
                # transition the request to an artefact build
                build = BuildFactory.generate(self.conf, request)
                # remove request from queue
                mgr.remove(request)
                build.run()
                mgr.archive(build)
            except SystemError as err:
                logger.error("Error while processing build: %s" % (err))
                sys.exit(1)
        logger.info("No build request available in queue, leaving")


class Fatbuildrctl(FatbuildrCliRun):

    def __init__(self):
        super().__init__()

        parser = argparse.ArgumentParser(description='Do something with fatbuildr.')
        #parser.add_argument('action', help='Action to perform', choices=['build', 'list', 'watch'])
        parser.add_argument('-v', '--version', dest='version', action='version', version='%(prog)s ' + __version__)
        parser.add_argument('--debug', dest='debug', action='store_true', help="Enable debug mode")
        parser.add_argument('-i', '--instance', dest='instance', help="Name of the instance")

        subparsers = parser.add_subparsers(help='Action to perform', dest='action', required=True)

        # create the parser for the images command
        parser_images = subparsers.add_parser('images', help='Manage build images')
        parser_images.add_argument('--create', action='store_true', help='Create the images')
        parser_images.add_argument('--update', action='store_true', help='Update the images')
        parser_images.add_argument('--force', action='store_true', help='Force creation of images even they already exist')
        parser_images.add_argument('--create-envs', action='store_true', help='Create the build environments in the images')
        parser_images.add_argument('--update-envs', action='store_true', help='Update the build environments in the images')
        parser_images.add_argument('-b', '--basedir', help='Artefacts definitions directory')
        parser_images.set_defaults(func=self._run_images)

        # create the parser for the build command
        parser_keyring = subparsers.add_parser('keyring', help='Manage signing keyring')
        parser_keyring.add_argument('--create', action='store_true', help='Create keyring')
        parser_keyring.add_argument('--show', action='store_true', help='Show keyring information')
        parser_keyring.add_argument('-b', '--basedir', help='Artefacts definitions directory')
        parser_keyring.set_defaults(func=self._run_keyring)

        # create the parser for the build command
        parser_build = subparsers.add_parser('build', help='Submit new build')
        parser_build.add_argument('-a', '--artefact', help='Artefact name', required=True)
        parser_build.add_argument('-d', '--distribution', help='Distribution name', required=True)
        parser_build.add_argument('-b', '--basedir', help='Artefacts repository directory', required=True)
        parser_build.add_argument('-n', '--name', help='Maintainer name', required=True)
        parser_build.add_argument('-e', '--email', help='Maintainer email', required=True)
        parser_build.add_argument('-m', '--msg', help='Build log message')
        parser_build.add_argument('-w', '--watch', action='store_true', help='Watch build log and wait until its end')
        parser_build.set_defaults(func=self._run_build)

        # create the parser for the list command
        parser_list = subparsers.add_parser('list', help='List builds')
        parser_list.add_argument('-p', '--pending', help='List pending builds')
        parser_list.set_defaults(func=self._run_list)

        # create the parser for the watch command
        parser_watch = subparsers.add_parser('watch', help='Watch build')
        parser_watch.add_argument('-b', '--build', help='ID of build to watch')
        parser_watch.set_defaults(func=self._run_watch)

        args = parser.parse_args()

        # setup logger
        if args.debug:
            logging_level = logging.DEBUG
        else:
            logging_level = logging.INFO
        logging.basicConfig(level=logging_level)

        self.conf = RuntimeConfCtl()
        self.load(args)

        # run the method corresponding to the provided action
        args.func()

    def load(self, args):
        super().load()

        self.conf.run.action = args.action

        if args.instance is not None:
            self.conf.run.instance = args.instance

        if args.action == 'images':
            if args.create is True:
                self.conf.run.operation = 'create'
            elif args.update is True:
                self.conf.run.operation = 'update'
            elif args.create_envs is True:
                self.conf.run.operation = 'create_envs'
            elif args.update_envs is True:
                self.conf.run.operation = 'update_envs'
            else:
                print("An operation on the images must be specified, type '%s images --help' for details" % (progname()))
                sys.exit(1)
            self.conf.run.force = args.force
            if self.conf.run.operation in ['create_envs', 'update_envs'] and args.basedir is None:
                print("The base directory must be specified to operate on build environments, type '%s images --help' for details" % (progname()))
                sys.exit(1)
            self.conf.run.basedir = args.basedir

        if args.action == 'keyring':
            if args.create is True:
                self.conf.run.operation = 'create'
            elif args.show is True:
                self.conf.run.operation = 'show'
            else:
                print("An operation on the keyring must be specified, type '%s keyring --help' for details" % (progname()))
                sys.exit(1)
            if self.conf.run.operation == 'create' and args.basedir is None:
                print("The base directory must be specified to create keyring, type '%s keyring --help' for details" % (progname()))
                sys.exit(1)
            self.conf.run.basedir = args.basedir

        elif args.action == 'build':
            self.conf.run.artefact = args.artefact
            self.conf.run.distribution = args.distribution
            self.conf.run.basedir = args.basedir
            self.conf.run.user_name = args.name
            self.conf.run.user_email = args.email
            self.conf.run.build_msg = args.msg
            self.conf.run.watch = args.watch

        elif args.action == 'watch':
            self.conf.run.build = args.build

        self.conf.dump()

    def _run_images(self):
        logger.debug("running images operation: %s" % (self.conf.run.operation))
        mgr = ImagesManager(self.conf)
        if self.conf.run.operation == 'create':
            mgr.create()
        elif self.conf.run.operation == 'update':
            mgr.update()
        elif self.conf.run.operation == 'create_envs':
            mgr.create_envs()
        elif self.conf.run.operation == 'update_envs':
            mgr.update_envs()

    def _run_keyring(self):
        logger.debug("running keyring operation: %s" % (self.conf.run.operation))
        mgr = KeyringManager(self.conf)
        if self.conf.run.operation == 'create':
            mgr.create()
        elif self.conf.run.operation == 'show':
            mgr.show()

    def _run_build(self):
        logger.debug("running build for package: %s instance: %s" % (self.conf.run.artefact, self.conf.run.instance))
        mgr = BuildsManager(self.conf)
        try:
            build_id = mgr.submit()
        except RuntimeError as err:
            logger.error("Error while submitting build: %s" % (err))
            sys.exit(1)
        if self.conf.run.watch:
            self._watch_build(build_id)

    def _run_list(self):
        logger.debug("running list")
        mgr = BuildsManager(self.conf)
        try:
            mgr.dump()
        except RuntimeError as err:
            logger.error("Error while listing builds: %s" % (err))
            sys.exit(1)

    def _watch_build(self, build_id):
        mgr = BuildsManager(self.conf)

        try:
            build = mgr.get(build_id)
        except RuntimeError as err:
            logger.error(err)
            sys.exit(1)

        warned_pending = False
        # if build is pending, wait
        while build.state == 'pending':
            if not warned_pending:
                logger.info("Build %s is pending, waiting for the build to start." % (build.id))
                warned_pending = True
            time.sleep(1)
            # poll build state again
            build = mgr.get(build_id)

        build.watch()

    def _run_watch(self):
        self._watch_build(self.conf.run.build)
