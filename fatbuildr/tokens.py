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

from .errors import FatbuildrRuntimeError, FatbuildrTokenError
from .log import logr

logger = logr(__name__)


class TokensManager:
    def __init__(self, conf, instance):
        self.conf = conf
        self.instance = instance
        self.path = self.conf.tokens.storage.joinpath(instance)
        self.encryption_key = None

    def load(self, create=False):
        """Load the encryption key for file saved in tokens manager directory.
        If create argument is True, the directory and the encryption key file
        are created if not present. Raises FatbuildrRuntimeError if create
        argument is False and the encryption key file is not found."""
        # Create instance tokens directory if missing
        if not self.path.exists() and create:
            logger.info("Creating tokens directory %s", self.path)
            self.path.mkdir()
            self.path.chmod(0o755)  # be umask agnostic
        # Generate instance tokens encryption key file if missing
        key_path = self.path.joinpath('key')
        if not key_path.exists():
            if create:
                logger.info(
                    "Generating tokens random encryption key file %s", key_path
                )
                with open(key_path, 'w+') as fh:
                    fh.write(secrets.token_hex(32))
                key_path.chmod(0o400)  # restrict access to encryption key
            else:
                raise FatbuildrRuntimeError(
                    f"Token encryption key file {key_path} not found"
                )
        # Load the instance tokens encryption key
        with open(key_path, 'r') as fh:
            self.encryption_key = fh.read()

    def decode(self, token):
        """Decode the given token with the encryption key an returns the user of
        this token."""
        try:
            payload = jwt.decode(
                token,
                self.encryption_key,
                audience='fatbuildr',
                algorithms=['HS256'],
            )
        except jwt.InvalidSignatureError:
            raise FatbuildrTokenError("token is invalid")
        except jwt.ExpiredSignatureError:
            raise FatbuildrTokenError("token is expired")
        return payload['sub']

    def generate(self, user):
        """Returns a JWT token for the given user, signed with the encryption
        key, valid for fatbuildr audience for 30 days."""
        return jwt.encode(
            {
                'iat': datetime.now(tz=timezone.utc),
                'exp': datetime.now(tz=timezone.utc) + timedelta(days=30),
                'aud': 'fatbuildr',
                'sub': user,
            },
            self.encryption_key,
            algorithm='HS256',
        )
