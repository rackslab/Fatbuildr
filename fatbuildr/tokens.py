#!/usr/bin/env python3
#
# Copyright (C) 2023 Rackslab
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

import secrets
from datetime import datetime, timezone, timedelta

import jwt

from .log import logr

logger = logr(__name__)


class TokensManager:
    def __init__(self, conf, instance):
        self.conf = conf
        self.instance = instance
        self.path = self.conf.tokens.storage.joinpath(instance.id)
        # Create instance tokens directory if missing
        if not self.path.exists():
            logger.info("Creating tokens directory %s", self.path)
            self.path.mkdir()
            self.path.chmod(0o755)  # be umask agnostic
        # Generate instance tokens encoding key file if missing
        key_path = self.path.joinpath('key')
        if not key_path.exists():
            logger.info(
                "Generating tokens random encoding key file %s", key_path
            )
            with open(key_path, 'w+') as fh:
                fh.write(secrets.token_hex(32))
            key_path.chmod(0o400)  # restrict access to encoding key
        # Load the instance tokens encoding key
        with open(key_path, 'r') as fh:
            self.encoding_key = fh.read()

    def generate(self, user):
        return jwt.encode(
            {
                'iat': datetime.now(tz=timezone.utc),
                'exp': datetime.now(tz=timezone.utc) + timedelta(days=30),
                'aud': 'fatbuildr',
                'sub': user,
            },
            self.encoding_key,
            algorithm='HS256',
        )
