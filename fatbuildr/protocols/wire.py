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

class WireBuild:

    def report(self):
        print("- id: %s" % (self.id))
        print("  state: %s" % (self.state))
        print("  source: %s" % (self.source))
        print("  place: %s" % (self.place))
        try:
            print("  logfile: %s" % (self.logfile))
        except AttributeError:
            pass
        print("  user: %s" % (self.user))
        print("  email: %s" % (self.email))
        print("  instance: %s" % (self.instance))
        print("  distribution: %s" % (self.distribution))
        print("  environment: %s" % (self.environment))
        print("  format: %s" % (self.format))
        print("  artefact: %s" % (self.artefact))
        print("  submission: %s" % (datetime.fromtimestamp(self.submission).isoformat(sep=' ',timespec='seconds')))
        print("  message: %s" % (self.message))

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
        _obj.source = build.source
        _obj.user = build.user
        _obj.email = build.email
        _obj.instance = build.instance
        _obj.distribution = build.distribution
        _obj.environment = build.environment
        _obj.format = build.format
        _obj.artefact = build.artefact
        _obj.submission = int(build.submission.timestamp())
        _obj.message = build.message
        return _obj
