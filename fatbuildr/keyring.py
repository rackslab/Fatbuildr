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

import gpg
import os
import string
import secrets
import sys
from datetime import datetime
import logging

from .pipelines import PipelinesDefs

logger = logging.getLogger(__name__)

class KeyringKey(object):

    def __init__(self, mgr):
        self.mgr = mgr
        self._key = None

    @property
    def fingerprint(self):
        return self._key.fpr

    @property
    def id(self):
        return self._key.keyid

    @property
    def algo(self):
        return gpg.core.pubkey_algo_string(self._key)

    @property
    def expires(self):
        expire = self._key.expires
        if expire == 0:
            return "never"
        return datetime.fromtimestamp(expire).isoformat(sep=' ',timespec='seconds')

    @property
    def creation(self):
        return datetime.fromtimestamp(self._key.timestamp).isoformat(sep=' ',timespec='seconds')


class KeyringSubKey(KeyringKey):

    def __init__(self, mgr, masterkey):
       super().__init__(mgr)
       self.masterkey = masterkey

    def create(self, ctx):
        """Create signing subkey in keyring context."""
        gen = ctx.create_subkey(key=self.masterkey._masterkey,
                                algorithm=self.mgr.algorithm,
                                expires=self.mgr.expires,
                                expires_in=self.mgr.expires_in,
                                sign=True,
                                passphrase=self.mgr.passphrase)
        # subkeys[0] is the masterkey, jump to subkey[1] to get the newly
        # created signing subkey.
        self._key = ctx.get_key(gen.fpr).subkeys[1]

    def load_from_keyring(self, _subkey):
        logger.debug("Loading subkey from keyring %s" % (self.mgr.homedir))
        self._key = _subkey


class KeyringMasterKey(KeyringKey):

    def __init__(self, mgr):
        super().__init__(mgr)
        self._masterkey = None
        self.subkey = KeyringSubKey(mgr, self)

    @property
    def userid(self):
        if len(self._masterkey.uids) != 1:
            raise ValueError("Multiple uids attached to key %s" % (self.fingerprint))
        return self._masterkey.uids[0].uid

    @property
    def last_update(self):
        last_update = self._masterkey.last_update
        if last_update == 0:
            return "never"
        return datetime.fromtimestamp(last_update).isoformat(sep=' ',timespec='seconds')

    def create(self, ctx):
        """Create masterkey in keyring context and load it."""
        # load userid from pipelines definitions
        gen = ctx.create_key(userid=self.mgr.pipelines_userid,
                             algorithm=self.mgr.algorithm,
                             expires=self.mgr.expires,
                             expires_in=self.mgr.expires_in,
                             passphrase=self.mgr.passphrase)
        self._masterkey = ctx.get_key(gen.fpr)
        # all keys details are stored in first masterkey subkey
        self._key = self._masterkey.subkeys[0]

    def load_from_keyring(self, ctx):
        """Load masterkey and its signing subkey from keyring context."""

        logger.debug("Loading masterkey from keyring %s" % (self.mgr.homedir))

        _keys_iter = ctx.keylist()

        self._masterkey = next(_keys_iter, None)

        if self._masterkey is None:
            raise RuntimeError("no key found in keyring")

        # The subkeys[0] is the masterkey. We except subkeys to have 2 members.

        if len(self._masterkey.subkeys) != 2:
            raise RuntimeError("multiple subkeys found in masterkey")

        self._key = self._masterkey.subkeys[0]
        self.subkey.load_from_keyring(self._masterkey.subkeys[1])

        if next(_keys_iter, None) is not None:
            raise RuntimeError("multiple keys found in keyring")

    def show(self):
        """Print information about the masterkey and its signing subkey."""

        print("masterkey:")
        print("  userid: %s" % (self.userid))
        print("  id: %s" % (self.id))
        print("  fingerprint: %s" % (self.fingerprint))
        print("  algo: %s" % (self.algo))
        print("  expires: %s" % (self.expires))
        print("  creation: %s" % (self.creation))
        print("  last_update: %s" % (self.last_update))
        print("  subkey:")
        print("    fingerprint: %s" % (self.subkey.fingerprint))
        print("    algo: %s" % (self.subkey.algo))
        print("    expires: %s" % (self.subkey.expires))
        print("    creation: %s" % (self.subkey.creation))


class KeyringManager(object):

    def __init__(self, conf):

        self.conf = conf
        self.homedir = os.path.join(self.conf.keyring.storage, self.conf.app.instance)
        self.passphrase_path = os.path.join(self.homedir, 'passphrase')
        self.algorithm = self.conf.keyring.type+str(self.conf.keyring.size)
        if type(self.conf.keyring.expires) is bool:
            self.expires = self.conf.keyring.expires
            self.expires_in = 0
        else:
            self.expires = True
            self.expires_in = self.conf.keyring.expires
        self.masterkey = KeyringMasterKey(self)

    @property
    def pipelines_userid(self):
        pipelines = PipelinesDefs(self.conf.app.basedir)
        return pipelines.gpg_name + ' <' + pipelines.gpg_email + '>'

    @property
    def passphrase(self):
        with open(self.passphrase_path, 'r') as fh:
            return fh.read()

    def create(self):

        # create homedir is missing
        if not os.path.exists(self.homedir):
            logger.info("Creating keyring directory %s" % (self.homedir))
            os.mkdir(self.homedir)
            # restrict access to keyring to root
            os.chmod(self.homedir, 0o700)

        # check if key already exist
        with gpg.Context(home_dir=self.homedir) as ctx:
            if any(ctx.keylist()):
                logger.error("Fatbuildr GPG key in %s already exists, leaving." % (self.homedir))
                sys.exit(1)

        # generate random passphrase and save it in file
        logger.info("Generating random passphrase in %s" % (self.homedir))
        alphabet = string.ascii_letters + string.digits
        passphrase = ''.join(secrets.choice(alphabet) for i in range(32))
        with open(self.passphrase_path, 'w+') as fh:
            fh.write(passphrase)
        os.chmod(self.passphrase_path, 0o400)  # restrict access to root read-only

        # generate GPG key with its subkey
        logger.info("Generating GPG key in %s" % (self.homedir))
        with gpg.Context(home_dir=self.homedir) as ctx:
            self.masterkey.create(ctx)
            logger.info("Key generated for user '{0}' with fingerprint {1}" \
                        .format(self.masterkey.userid,
                                self.masterkey.fingerprint))
            self.masterkey.subkey.create(ctx)
            logger.info("Subkey generated for signature with fingerprint {0}" \
                        .format(self.masterkey.subkey.fingerprint))


    def show(self):
        with gpg.Context(home_dir=self.homedir) as ctx:
            try:
                self.masterkey.load_from_keyring(ctx)
            except RuntimeError as err:
                logger.error("Error while loading keyring %s: %s" % (self.homedir, err))
            else:
                self.masterkey.show()
