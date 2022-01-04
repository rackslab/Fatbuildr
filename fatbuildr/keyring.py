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
import logging

from .pipelines import PipelinesDefs

logger = logging.getLogger(__name__)


class KeyringManager(object):

    def __init__(self, conf):
        self.conf = conf
        self.homedir = os.path.join(self.conf.keyring.storage, self.conf.ctl.instance)
        self.passphrase_path = os.path.join(self.homedir, 'passphrase')
        pipelines = PipelinesDefs(self.conf.ctl.basedir)
        self.userid = pipelines.gpg_name + ' <' + pipelines.gpg_email + '>'
        self.algorithm = self.conf.keyring.type+str(self.conf.keyring.size)
        if type(self.conf.keyring.expires) is bool:
            self.expires = self.conf.keyring.expires
            self.expires_in = 0
        else:
            self.expires = True
            self.expires_in = self.conf.keyring.expires

    def create(self):

        # create homedir is missing
        if not os.path.exists(self.homedir):
            logger.info("Creating keyring directory %s" % (self.homedir))
            os.mkdir(self.homedir)

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
        os.chmod(self.passphrase_path, 0o400)  # restrict access to RO

        # generate GPG key with its subkey
        logger.info("Generating GPG key in %s" % (self.homedir))
        with gpg.Context(home_dir=self.homedir) as ctx:
            genmasterkey = ctx.create_key(userid=self.userid,
                                          algorithm=self.algorithm,
                                          expires=self.expires,
                                          expires_in=self.expires_in,
                                          passphrase=passphrase)
            logger.info("Key generated with fingerprint {0}.".format(genmasterkey.fpr))
            masterkey = ctx.get_key(genmasterkey.fpr)
            subkey = ctx.create_subkey(key=masterkey,
                                       algorithm=self.algorithm,
                                       expires=self.expires,
                                       expires_in=self.expires_in,
                                       sign=True,
                                       passphrase=passphrase)
            logger.info("Subkey generated for signature with fingerprint {0}".format(subkey.fpr))
