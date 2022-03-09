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

import string
import secrets
from datetime import datetime

import gpg

from .protocols.exports import ExportableType, ExportableField
from .utils import runcmd
from .log import logr

logger = logr(__name__)


class KeyringKey(object):
    def __init__(self, keyring):
        self.keyring = keyring
        self._key = None

    @property
    def fingerprint(self):
        return self._key.fpr

    @property
    def keygrip(self):
        return self._key.keygrip

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
        return datetime.fromtimestamp(expire).isoformat(
            sep=' ', timespec='seconds'
        )

    @property
    def creation(self):
        return datetime.fromtimestamp(self._key.timestamp).isoformat(
            sep=' ', timespec='seconds'
        )


class KeyringSubKey(KeyringKey, ExportableType):
    EXFIELDS = {
        ExportableField('fingerprint'),
        ExportableField('algo'),
        ExportableField('expires'),
        ExportableField('creation'),
    }

    def __init__(self, keyring, masterkey):
        KeyringKey.__init__(self, keyring)
        self.masterkey = masterkey

    def create(self, ctx):
        """Create signing subkey in keyring context."""
        gen = ctx.create_subkey(
            key=self.masterkey._masterkey,
            algorithm=self.keyring.algorithm,
            expires=self.keyring.expires,
            expires_in=self.keyring.expires_in,
            sign=True,
            passphrase=self.keyring.passphrase,
        )
        # subkeys[0] is the masterkey, jump to subkey[1] to get the newly
        # created signing subkey.
        self._key = ctx.get_key(gen.fpr).subkeys[1]

    def load_from_keyring(self, _subkey):
        logger.debug("Loading subkey from keyring %s" % (self.keyring.homedir))
        self._key = _subkey


class KeyringMasterKey(KeyringKey, ExportableType):

    EXFIELDS = {
        ExportableField('userid'),
        ExportableField('id'),
        ExportableField('fingerprint'),
        ExportableField('algo'),
        ExportableField('expires'),
        ExportableField('creation'),
        ExportableField('last_update'),
        ExportableField('subkey', KeyringSubKey),
    }

    def __init__(self, keyring):
        KeyringKey.__init__(self, keyring)
        self._masterkey = None
        self.subkey = KeyringSubKey(keyring, self)

    @property
    def userid(self):
        if len(self._masterkey.uids) != 1:
            raise ValueError(
                "Multiple uids attached to key %s" % (self.fingerprint)
            )
        return self._masterkey.uids[0].uid

    @property
    def last_update(self):
        last_update = self._masterkey.last_update
        if last_update == 0:
            return "never"
        return datetime.fromtimestamp(last_update).isoformat(
            sep=' ', timespec='seconds'
        )

    def create(self, ctx, userid):
        """Create masterkey in keyring context and load it."""
        gen = ctx.create_key(
            userid=userid,
            algorithm=self.keyring.algorithm,
            expires=self.keyring.expires,
            expires_in=self.keyring.expires_in,
            passphrase=self.keyring.passphrase,
        )
        self._masterkey = ctx.get_key(gen.fpr)
        # all keys details are stored in first masterkey subkey
        self._key = self._masterkey.subkeys[0]

    def load_from_keyring(self, ctx):
        """Load masterkey and its signing subkey from keyring context."""

        logger.debug("Loading masterkey from keyring %s", self.keyring.homedir)

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


class InstanceKeyring:
    def __init__(self, conf, instance):

        self.conf = conf
        self.instance = instance
        self.homedir = self.conf.keyring.storage.joinpath(instance.id)
        self.passphrase_path = self.homedir.joinpath('passphrase')
        self.algorithm = self.conf.keyring.type + str(self.conf.keyring.size)
        if type(self.conf.keyring.expires) is bool:
            self.expires = self.conf.keyring.expires
            self.expires_in = 0
        else:
            self.expires = True
            self.expires_in = self.conf.keyring.expires
        self.masterkey = KeyringMasterKey(self)

    @property
    def passphrase(self):
        with open(self.passphrase_path, 'r') as fh:
            return fh.read()

    def create(self):

        # create homedir is missing
        if not self.homedir.exists():
            logger.info("Creating keyring directory %s", self.homedir)
            self.homedir.mkdir()
            # restrict access to keyring to root
            self.homedir.chmod(0o700)

        # check if key already exist
        with gpg.Context(home_dir=str(self.homedir)) as ctx:
            if any(ctx.keylist()):
                raise RuntimeError(f"GPG key in {self.homedir} already exists.")

        # generate random passphrase and save it in file
        logger.info("Generating random passphrase in %s", self.homedir)
        alphabet = string.ascii_letters + string.digits
        passphrase = ''.join(secrets.choice(alphabet) for i in range(32))
        with open(self.passphrase_path, 'w+') as fh:
            fh.write(passphrase)
        # restrict access to root read-only
        self.passphrase_path.chmod(0o400)

        # generate GPG key with its subkey
        logger.info("Generating GPG key in %s", self.homedir)
        with gpg.Context(home_dir=str(self.homedir)) as ctx:
            self.masterkey.create(ctx, self.instance.userid)
            logger.info(
                "Key generated for user '%s' with fingerprint %s",
                self.masterkey.userid,
                self.masterkey.fingerprint,
            )
            self.masterkey.subkey.create(ctx)
            logger.info(
                "Subkey generated for signature with fingerprint %s",
                self.masterkey.subkey.fingerprint,
            )

    def load(self):
        with gpg.Context(home_dir=str(self.homedir)) as ctx:
            try:
                self.masterkey.load_from_keyring(ctx)
            except RuntimeError as err:
                logger.error(
                    "Error while loading keyring %s: %s", self.homedir, err
                )

    def export(self):
        """Return string representation of armored public key of the keyring
        masterkey."""
        with gpg.Context(home_dir=str(self.homedir), armor=True) as ctx:
            try:
                self.masterkey.load_from_keyring(ctx)
                return ctx.key_export(self.masterkey.fingerprint).decode()
            except RuntimeError as err:
                logger.error(
                    "Error while loading keyring %s: %s", self.homedir, err
                )

    def _passphrase_cb(self, hint, dest, prev_bad, hook=None):
        """Method with signature expected by gpg Context.set_passphrase_db()
        func"""
        return self.passphrase.encode()

    def _renew_key(self, ctx, key, duration, subkey=False):
        """Extend either master or subkey in the given context for the given
        duration using interactive key editor."""
        commands = ["expire", duration, "save", "quit"]
        if subkey:
            commands.insert(0, "key 1")

        cmd_id = 0

        def edit_fnc(keyword, args):
            nonlocal cmd_id
            if 'GET' not in keyword:
                return None
            try:
                cmd = commands[cmd_id]
                logger.debug("Sending interactive command %s", cmd)
                cmd_id += 1
                return cmd
            except EOFError:
                return "quit"

        ctx.interact(key, edit_fnc)

    def renew(self, duration):
        """Extend keyring expiry date with the given duration, for both the
        masterkey and the subkey."""
        with gpg.Context(
            home_dir=str(self.homedir),
            pinentry_mode=gpg.constants.PINENTRY_MODE_LOOPBACK,
        ) as ctx:
            ctx.set_passphrase_cb(self._passphrase_cb)
            keys = list(ctx.keylist())
            if len(keys) == 0:
                raise RuntimeError("No GPG key found in keyring")
            if len(keys) > 1:
                raise RuntimeError("More than one GPG key found in keyring")
            key = keys[0]
            self._renew_key(ctx, key, duration)
            self._renew_key(ctx, key, duration, subkey=True)

        # reload the keyring to get changes
        self.load()

    def load_agent(self):
        """Load GPG signing subkey in gpg-agent so reprepro can use the key
        non-interactively."""

        # First stop agent if running (ie. socket is present), as it may not
        # has been started to allow preset.
        gpgagent_sock_path = self.homedir.joinpath('S.gpg-agent')
        if gpgagent_sock_path.exists():
            cmd = [
                'gpgconf',
                '--kill',
                '--homedir',
                self.homedir,
                'gpg-agent',
            ]
            runcmd(cmd)

        # Start agent with --allow-preset-passphrase so the key can be loaded
        # non-interactively.
        cmd = [
            'gpg-agent',
            '--homedir',
            self.homedir,
            '--allow-preset-passphrase',
            '--daemon',
        ]
        runcmd(cmd)

        # Load GPG in agent using the passphrase
        cmd = [
            '/usr/lib/gnupg/gpg-preset-passphrase',
            '--preset',
            self.masterkey.subkey.keygrip,
        ]
        runcmd(
            cmd,
            env={'GNUPGHOME': str(self.homedir)},
            input=self.passphrase.encode(),
        )
