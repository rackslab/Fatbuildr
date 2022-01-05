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
from ..jobs import JobManager
from ..cleanup import CleanupRegistry

logger = logging.getLogger(__name__)


def progname():
    """Return the name of the program."""
    return os.path.basename(sys.argv[0])


class FatbuildrCliApp(object):

    @classmethod
    def run(cls):
        """Instanciate and execute the CliApp."""
        atexit.register(CleanupRegistry.clean)
        app = cls()

    def __init__(self):

        self.conf = None

    def load(self):

        try:
            self.conf.load()  # load configuration file
        except ValueError as err:
            logger.error("Error while loading configuration: %s" % (err))
            sys.exit(1)

        self.conf.dump()


class Fatbuildrd(FatbuildrCliApp):

    def __init__(self):
        super().__init__()

        parser = argparse.ArgumentParser(description='Do something with fatbuildr.')
        parser.add_argument('-v', '--version', dest='version', action='version', version='%(prog)s ' + __version__)
        parser.add_argument('--debug', dest='debug', action='store_true', help="Enable debug mode")

        args = parser.parse_args()

        # setup logger
        if args.debug:
            logging_level = logging.DEBUG
        else:
            logging_level = logging.INFO
        logging.basicConfig(level=logging_level)

        self.conf = RuntimeConfd()
        self.load()
        self._run()

    def _run(self):
        logger.debug("Running fatbuildrd")
        mgr = JobManager(self.conf)
        try:
            for job in mgr.load():
                logger.info("Processing job %s" % (job.id))
                mgr.remove(job)
                time.sleep(1)
        except RuntimeError as err:
            logger.error("Error while processing job: %s" % (err))
            sys.exit(1)


class Fatbuildrctl(FatbuildrCliApp):

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
        parser_build = subparsers.add_parser('build', help='Submit new build job')
        parser_build.add_argument('-a', '--artefact', help='Artefact name', required=True)
        parser_build.add_argument('-d', '--distribution', help='Distribution name', required=True)
        parser_build.add_argument('-b', '--basedir', help='Artefacts repository directory', required=True)
        parser_build.set_defaults(func=self._run_build)

        # create the parser for the list command
        parser_list = subparsers.add_parser('list', help='List build jobs')
        parser_list.add_argument('-p', '--pending', help='List pending jobs')
        parser_list.set_defaults(func=self._run_list)

        # create the parser for the watch command
        parser_watch = subparsers.add_parser('watch', help='Watch build jobs')
        parser_watch.add_argument('--job', help='Job to watch')
        parser_watch.set_defaults(func=self._run_list)

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

        self.conf.app.action = args.action

        if args.instance is not None:
            self.conf.app.instance = args.instance

        if args.action == 'images':
            if args.create is True:
                self.conf.app.operation = 'create'
            elif args.update is True:
                self.conf.app.operation = 'update'
            elif args.create_envs is True:
                self.conf.app.operation = 'create_envs'
            elif args.update_envs is True:
                self.conf.app.operation = 'update_envs'
            else:
                print("An operation on the images must be specified, type '%s images --help' for details" % (progname()))
                sys.exit(1)
            self.conf.app.force = args.force
            if self.conf.app.operation in ['create_envs', 'update_envs'] and args.basedir is None:
                print("The base directory must be specified to operate on build environments, type '%s images --help' for details" % (progname()))
                sys.exit(1)
            self.conf.app.basedir = args.basedir

        if args.action == 'keyring':
            if args.create is True:
                self.conf.app.operation = 'create'
            elif args.show is True:
                self.conf.app.operation = 'show'
            else:
                print("An operation on the keyring must be specified, type '%s keyring --help' for details" % (progname()))
                sys.exit(1)
            if self.conf.app.operation == 'create' and args.basedir is None:
                print("The base directory must be specified to create keyring, type '%s keyring --help' for details" % (progname()))
                sys.exit(1)
            self.conf.app.basedir = args.basedir

        elif args.action == 'build':
            self.conf.app.artefact = args.artefact
            self.conf.app.distribution = args.distribution
            self.conf.app.basedir = args.basedir

        self.conf.dump()

    def _run_images(self):
        logger.debug("running images operation: %s" % (self.conf.app.operation))
        mgr = ImagesManager(self.conf)
        if self.conf.app.operation == 'create':
            mgr.create()
        elif self.conf.app.operation == 'update':
            mgr.update()
        elif self.conf.app.operation == 'create_envs':
            mgr.create_envs()
        elif self.conf.app.operation == 'update_envs':
            mgr.update_envs()

    def _run_keyring(self):
        logger.debug("running keyring operation: %s" % (self.conf.app.operation))
        mgr = KeyringManager(self.conf)
        if self.conf.app.operation == 'create':
            mgr.create()
        elif self.conf.app.operation == 'show':
            mgr.show()

    def _run_build(self):
        logger.debug("running build for package: %s instance: %s" % (self.conf.app.artefact, self.conf.app.instance))
        mgr = JobManager(self.conf)
        try:
            mgr.submit()
        except RuntimeError as err:
            logger.error("Error while submitting build job: %s" % (err))
            sys.exit(1)

    def _run_list(self):
        logger.debug("running list")
        mgr = JobManager(self.conf)
        try:
            mgr.dump()
        except RuntimeError as err:
            logger.error("Error while submitting build job: %s" % (err))
            sys.exit(1)

    def _run_watch(self):
        raise NotImplementedError
