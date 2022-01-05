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

from ..version import __version__
from ..conf import RuntimeConfCtl
from ..images import ImagesManager
from ..keyring import KeyringManager

logger = logging.getLogger(__name__)


def progname():
    """Return the name of the program."""
    return os.path.basename(sys.argv[0])


class FatbuildrCliApp(object):

    @classmethod
    def run(cls):
        """Instanciate and execute the CliApp."""
        app = cls()


class Fatbuildrd(FatbuildrCliApp):

    def __init__(self):
        print("running fatbuildrd")


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
        parser_build.add_argument('-p', '--package', help='Package name', required=True)
        parser_build.add_argument('-b', '--basedir', help='Artefacts definitions directory', required=True)
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

        try:
            self.conf.load()  # load configuration file
        except ValueError as err:
            logger.error("Error while loading configuration: %s" % (err))
            sys.exit(1)

        self.conf.ctl.action = args.action

        if args.instance is not None:
            self.conf.ctl.instance = args.instance

        if args.action == 'images':
            if args.create is True:
                self.conf.ctl.operation = 'create'
            elif args.update is True:
                self.conf.ctl.operation = 'update'
            elif args.create_envs is True:
                self.conf.ctl.operation = 'create_envs'
            elif args.update_envs is True:
                self.conf.ctl.operation = 'update_envs'
            else:
                print("An operation on the images must be specified, type '%s images --help' for details" % (progname()))
                sys.exit(1)
            self.conf.ctl.force = args.force
            if self.conf.ctl.operation in ['create_envs', 'update_envs'] and args.basedir is None:
                print("The base directory must be specified to operate on build environments, type '%s images --help' for details" % (progname()))
                sys.exit(1)
            self.conf.ctl.basedir = args.basedir

        if args.action == 'keyring':
            if args.create is True:
                self.conf.ctl.operation = 'create'
            elif args.show is True:
                self.conf.ctl.operation = 'show'
            else:
                print("An operation on the keyring must be specified, type '%s keyring --help' for details" % (progname()))
                sys.exit(1)
            if self.conf.ctl.operation == 'create' and args.basedir is None:
                print("The base directory must be specified to create keyring, type '%s keyring --help' for details" % (progname()))
                sys.exit(1)
            self.conf.ctl.basedir = args.basedir

        elif args.action == 'build':
            self.conf.ctl.package = args.package
            self.conf.ctl.basedir = args.basedir

        self.conf.dump()

    def _run_images(self):
        logger.debug("running images operation: %s" % (self.conf.ctl.operation))
        mgr = ImagesManager(self.conf)
        if self.conf.ctl.operation == 'create':
            mgr.create()
        elif self.conf.ctl.operation == 'update':
            mgr.update()
        elif self.conf.ctl.operation == 'create_envs':
            mgr.create_envs()
        elif self.conf.ctl.operation == 'update_envs':
            mgr.update_envs()

    def _run_keyring(self):
        logger.debug("running keyring operation: %s" % (self.conf.ctl.operation))
        mgr = KeyringManager(self.conf)
        if self.conf.ctl.operation == 'create':
            mgr.create()
        elif self.conf.ctl.operation == 'show':
            mgr.show()

    def _run_build(self):
        logger.debug("running build for package: %s instance: %s" % (self.conf.ctl.package, self.conf.ctl.instance))

    def _run_list(self):
        raise NotImplementedError

    def _run_watch(self):
        raise NotImplementedError
