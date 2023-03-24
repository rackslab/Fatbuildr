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
import base64

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
                audience=self.conf.tokens.audience,
                algorithms=[self.conf.tokens.algorithm],
            )
        except jwt.InvalidSignatureError:
            raise FatbuildrTokenError("token is invalid")
        except jwt.ExpiredSignatureError:
            raise FatbuildrTokenError("token is expired")
        return payload['sub']

    def generate(self, user):
        """Returns a JWT token for the given user, signed with the encryption
        key, valid for the configured audience and duration."""
        return jwt.encode(
            {
                'iat': datetime.now(tz=timezone.utc),
                'exp': datetime.now(tz=timezone.utc)
                + timedelta(days=self.conf.tokens.duration),
                'aud': self.conf.tokens.audience,
                'sub': user,
            },
            self.encryption_key,
            algorithm=self.conf.tokens.algorithm,
        )


class ClientToken:
    """Class to hold information about a Fatbuildr JWT token."""

    def __init__(self, path, uri, raw, iat, exp, aud, sub):
        self.path = path
        self.uri = uri
        self.raw = raw
        self.iat = iat
        self.exp = exp
        self.aud = aud
        self.sub = sub

    def __str__(self):
        return (
            f"path: {self.path}\n"
            f"uri: {self.uri}\n"
            f"user: {self.sub}\n"
            f"issued at: {datetime.fromtimestamp(self.iat).isoformat()}\n"
            f"expiration: {datetime.fromtimestamp(self.exp).isoformat()}\n"
            f"audience: {self.aud}"
        )


class ClientTokensManager:
    """Class to manager JWT tokens in a given path on client side."""

    EXTENSION = '.token'

    def __init__(self, path):
        self.path = path

    def tokens(self):
        """Returns the list of ClientTokens available in the manager path."""
        return [
            ClientToken(
                token_path,
                self._path_token_uri(token_path),
                *self._load_path(token_path),
            )
            for token_path in self.path.glob('*' + self.EXTENSION)
        ]

    def _path_token_uri(self, path):
        return base64.b64decode(path.stem.encode()).decode()

    def _uri_token_filename(self, uri):
        return base64.b64encode(uri.encode()).decode() + self.EXTENSION

    def _load_path(self, path):
        if not path.exists():
            raise FatbuildrRuntimeError(f"token file {path} not found")
        with open(path) as fh:
            token = fh.read().strip()
        payload = jwt.decode(token, options={'verify_signature': False})
        return (
            token,
            payload['iat'],
            payload['exp'],
            payload['aud'],
            payload['sub'],
        )

    def load(self, uri):
        """Loads the token file in manager path associated to the given URI and
        return its raw value. If for any reason the token cannot be loaded for
        this URI, returns None."""
        token_path = self.path.joinpath(self._uri_token_filename(uri))
        try:
            token = ClientToken(token_path, uri, *self._load_path(token_path))
        except FatbuildrRuntimeError as err:
            logger.debug("unable to load token for uri %s: %s", uri, err)
            return None
        else:
            logger.debug("loaded token file %s", token_path)
            return token.raw

    def save(self, uri, token):
        """Save the given token in manager path with a filename associated to
        the given URI."""
        if not self.path.exists():
            try:
                logger.debug("creating user's tokens directory %s", self.path)
                self.path.mkdir()
                self.path.chmod(0o700)
            except FileNotFoundError as err:
                # Parent does not exist, fail instead of potentially messing
                # with user's files by creating all missing parents directories
                raise FatbuildrRuntimeError(
                    f"unable to create user's tokens directory: {err}"
                )
        token_path = self.path.joinpath(self._uri_token_filename(uri))
        with open(token_path, 'w+') as fh:
            fh.write(token)
        logger.info("token saved in file %s", token_path)
        token_path.chmod(0o600)  # restrict permission on token file to user
