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

from ..registry.formats import RegistryArtefact
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


class WireBuild:
    def report(self):
        print("- id: %s" % (self.id))
        print("  state: %s" % (self.state))
        print("  place: %s" % (self.place))
        try:
            print("  logfile: %s" % (self.logfile))
        except AttributeError:
            pass
        print("  user: %s" % (self.user))
        print("  email: %s" % (self.email))
        print("  distribution: %s" % (self.distribution))
        print("  derivative: %s" % (self.derivative))
        print("  environment: %s" % (self.environment))
        print("  format: %s" % (self.format))
        print("  artefact: %s" % (self.artefact))
        print(
            "  submission: %s"
            % (
                datetime.fromtimestamp(self.submission).isoformat(
                    sep=' ', timespec='seconds'
                )
            )
        )
        print("  message: %s" % (self.message))

    def to_dict(self):
        result = {
            'id': self.id,
            'state': self.state,
            'place': self.place,
            'user': self.user,
            'email': self.email,
            'distribution': self.distribution,
            'derivative': self.derivative,
            'environment': self.environment,
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
    def load_from_build(cls, build):
        _obj = cls()
        _obj.id = build.id
        _obj.state = build.state
        _obj.place = build.place
        try:
            _obj.logfile = build.logfile
        except AttributeError:
            _obj.logfile = None
        _obj.user = build.user
        _obj.email = build.email
        if build.distribution is None:
            _obj.distribution = 'none'
        else:
            _obj.distribution = build.distribution
        _obj.derivative = build.derivative
        if build.environment is None:
            _obj.environment = 'none'
        else:
            _obj.environment = build.environment
        _obj.format = build.format
        _obj.artefact = build.artefact
        _obj.submission = int(build.submission.timestamp())
        _obj.message = build.message
        return _obj

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
        if json['distribution'] is None:
            _obj.distribution = 'none'
        else:
            _obj.distribution = json['distribution']
        _obj.derivative = json['derivative']
        if json['environment'] is None:
            _obj.environment = 'none'
        else:
            _obj.environment = json['environment']
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

    @classmethod
    def load_from_artefact(cls, artefact):
        _obj = cls()
        _obj.name = artefact.name
        _obj.architecture = artefact.architecture
        _obj.version = artefact.version
        return _obj

    @staticmethod
    def convert_to_artefact(artefact):
        return RegistryArtefact(
            artefact.name, artefact.architecture, artefact.version
        )


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
