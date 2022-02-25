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
        print(f"- name: {self.name}")
        print(f"  architecture: {self.architecture}")
        print(f"  version: {self.version}")

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


class WireKeyring:
    def report(self):
        print("masterkey:")
        print(f"  userid: {self.userid}")
        print(f"  id: {self.id}")
        print(f"  fingerprint: {self.fingerprint}")
        print(f"  algo: {self.algo}")
        print(f"  expires: {self.expires}")
        print(f"  creation: {self.creation}")
        print(f"  last update: {self.last_update}")
        print("  subkey:")
        print(f"    fingerprint: {self.subkey.fingerprint}")
        print(f"    algo: {self.subkey.algo}")
        print(f"    expires: {self.subkey.expires}")
        print(f"    creation: {self.subkey.creation}")
