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

from . import FatbuildrCliRun
from ..conf import RuntimeConfWeb
from ..version import __version__
from ..protocols.crawler import register_protocols
from ..web import WebApp
from ..log import logr

logger = logr(__name__)


class FatbuildrWeb(FatbuildrCliRun):
    def __init__(self):
        parser = argparse.ArgumentParser(
            description='Fatbuilrdr web interface.'
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
            '-i',
            '--instance',
            help="Instance to serve (default: %(default)s)",
            default='all',
        )
        args = parser.parse_args()

        logger.setup(args.debug, fulldebug=False)

        self.conf = RuntimeConfWeb()
        self.load(args)
        self.app = WebApp(self.conf, args.instance)
        self.app.run()

    def load(self, args):
        super().load_conf()

        register_protocols()

        if args.debug:
            self.conf.run.debug = True

        self.conf.dump()
