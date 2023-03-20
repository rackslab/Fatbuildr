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

import mod_wsgi

from fatbuildr.protocols.http.server import WebApp
from fatbuildr.conf import RuntimeConfWeb
from fatbuildr.protocols.crawler import register_protocols
from fatbuildr.log import logr

# Setup initial logger. Name is forced as there is no way to control module
# name __name__ defined by mod_wsgi.
logger = logr('fatbuildr.wsgi')
logger.setup(False, fulldebug=False)

# Register protocols with types
register_protocols()

# Load configuratio file
conf = RuntimeConfWeb()
conf.load()

# if debug is enabled in configuration file, setup logger at debug level
if conf.run.debug:
    logger.ensure_debug()

conf.dump()

# Extract instance name from last part of WSGI process group, after the last
# dash. For example, for process group 'fatbuildrweb-default', the instance
# name 'default' is extracted.
instance = mod_wsgi.process_group.rsplit('-',1)[1]

# Initialize WSGI application
application = WebApp(conf, instance)
