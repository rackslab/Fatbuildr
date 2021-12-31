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
import logging

from ..version import __version__
from ..conf import RuntimeConf

logger = logging.getLogger(__name__)

class FatbuildrCliApp(object):

    @classmethod
    def run(cls):
        """Instanciate and execute the CliApp."""
        app = cls()
        app.exec()

    def __init__(self):
        self.conf = RuntimeConf()

    def load(self):
        self.conf.load()

class Fatbuildrd(FatbuildrCliApp):

    def __init__(self):
        super().__init__()

    def exec(self):
        print("running fatbuildrd")


class Fatbuildrctl(FatbuildrCliApp):

    def __init__(self):
        super().__init__()

    def exec(self):
        parser = argparse.ArgumentParser(description='Do something with fatbuildr.')
        #parser.add_argument('action', help='Action to perform', choices=['build', 'list', 'watch'])
        parser.add_argument('-v', '--version', dest='version', action='version', version='%(prog)s ' + __version__)
        parser.add_argument('--debug', dest='debug', action='store_true', help="Enable debug mode")

        subparsers = parser.add_subparsers(help='Action to perform', required=True)

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

        try:
            args = parser.parse_args()
        except TypeError:
            # type error is raised when no subparser action is given
            print("Action must be choosen, see --help for details")
            sys.exit(1)

        # setup logger
        if args.debug:
            logging_level = logging.DEBUG
        else:
            logging_level = logging.INFO
        logging.basicConfig(level=logging_level)

        self.load()
        args.func(args)

    def _run_build(self, args):
        logging.info("running build for package: %s" % (args.package))

    def _run_list(self, args):
        raise NotImplementedError

    def _run_watch(self, args):
        raise NotImplementedError
