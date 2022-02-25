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

from datetime import datetime

from ..log import logr

logger = logr(__name__)


class WireInstance:
    def to_dict(self):
        result = {
            'id': self.id,
            'name': self.name,
            'userid': self.userid,
        }
        return result

    @classmethod
    def load_from_instance(cls, instance):
        _obj = cls()
        _obj.id = instance.id
        _obj.name = instance.name
        _obj.userid = instance.userid
        return _obj

    @classmethod
    def load_from_json(cls, json):
        _obj = cls()
        _obj.id = json['id']
        _obj.name = json['name']
        _obj.userid = json['userid']
        return _obj


class WireRunnableTask:
    def report(self):
        print(f"- id: {self.id}")
        print(f"  name: {self.name}")
        print(f"  state: {self.state}")
        print(f"  place: {self.place}")
        print(f"  logfile: {self.logfile}")
        print(
            "  submission: ",
            self.submission.isoformat(sep=' ', timespec='seconds'),
        )
        if self.name == "artefact build":
            print(f"  user: {self.user}")
            print(f"  email: {self.email}")
            print(f"  distribution: {self.distribution}")
            print(f"  derivative: {self.derivative}")
            print(f"  format: {self.format}")
            print(f"  artefact: {self.artefact}")
            print(f"  message: {self.message}")
        elif self.name == "artefact deletion":
            print("  artefact:")
            print(f"    name: {self.artefact.name}")
            print(f"    architecture: {self.artefact.architecture}")
            print(f"    version: {self.artefact.version}")

    def to_dict(self):
        result = {
            'id': self.id,
            'state': self.state,
            'place': self.place,
            'user': self.user,
            'email': self.email,
            'distribution': self.distribution,
            'derivative': self.derivative,
            'format': self.format,
            'artefact': self.artefact,
            'submission': self.submission,
            'message': self.message,
        }
        try:
            result['logfile'] = self.logfile
        except AttributeError:
            result['logfile'] = None
        return result

    @classmethod
    def load_from_json(cls, json):
        _obj = cls()
        _obj.id = json['id']
        _obj.state = json['state']
        _obj.place = json['place']
        try:
            _obj.logfile = json['logfile']
        except AttributeError:
            _obj.logfile = None
        _obj.user = json['user']
        _obj.email = json['email']
        _obj.distribution = json['distribution']
        _obj.derivative = json['derivative']
        _obj.format = json['format']
        _obj.artefact = json['artefact']
        _obj.submission = json['submission']
        _obj.message = json['message']
        return _obj


class WireArtefact:
    def report(self):
        print("- name: %s" % (self.name))
        print("  architecture: %s" % (self.architecture))
        print("  version: %s" % (self.version))

    def to_dict(self):
        return {
            'name': self.name,
            'architecture': self.architecture,
            'version': self.version,
        }


class WireChangelogEntry:
    def to_dict(self):
        return {
            'version': self.version,
            'author': self.author,
            'date': self.date,
            'changes': self.changes,
        }

    @classmethod
    def load_from_entry(cls, entry):
        _obj = cls()
        _obj.version = entry.version
        _obj.author = entry.author
        _obj.date = entry.date
        _obj.changes = entry.changes
        return _obj


class WireKeyring:
    def report(self):
        print("masterkey:")
        print("  userid: %s" % (self.userid))
        print("  id: %s" % (self.id))
        print("  fingerprint: %s" % (self.fingerprint))
        print("  algo: %s" % (self.algo))
        print("  expires: %s" % (self.expires))
        print("  creation: %s" % (self.creation))
        print("  last update: %s" % (self.last_update))
        print("  subkey:")
        print("    fingerprint: %s" % (self.subkey_fingerprint))
        print("    algo: %s" % (self.subkey_algo))
        print("    expires: %s" % (self.subkey_expires))
        print("    creation: %s" % (self.subkey_creation))

    @classmethod
    def load_from_keyring(cls, keyring):
        _obj = cls()
        _obj.userid = keyring.userid
        _obj.id = keyring.id
        _obj.fingerprint = keyring.fingerprint
        _obj.algo = keyring.algo
        _obj.expires = keyring.expires
        _obj.creation = keyring.creation
        _obj.last_update = keyring.last_update
        _obj.subkey_fingerprint = keyring.subkey.fingerprint
        _obj.subkey_algo = keyring.subkey.algo
        _obj.subkey_expires = keyring.subkey.expires
        _obj.subkey_creation = keyring.subkey.creation
        return _obj
