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


class WireData:
    pass


class WireInstance(WireData):
    pass


class WireRunnableTask(WireData):
    def report(self):
        print(f"- id: {self.id}")
        print(f"  name: {self.name}")
        print(f"  state: {self.state}")
        print(f"  place: {self.place}")
        print(
            "  submission: ",
            self.submission.isoformat(sep=' ', timespec='seconds'),
        )
        print("  io:")
        print(f"    interactive: {self.io.interactive}")
        print(f"    input: {self.io.fifo_input}")
        print(f"    output: {self.io.fifo_output}")
        print(f"    logfile: {self.io.logfile}")
        if self.name == "artifact build":
            print(f"  user: {self.user}")
            print(f"  email: {self.email}")
            print(f"  distribution: {self.distribution}")
            print(f"  architectures: {' '.join(self.architectures)}")
            print(f"  derivative: {self.derivative}")
            print(f"  format: {self.format}")
            print(f"  artifact: {self.artifact}")
            print(f"  message: {self.message}")
        elif self.name == "artifact deletion":
            print("  artifact:")
            print(f"    name: {self.artifact.name}")
            print(f"    architecture: {self.artifact.architecture}")
            print(f"    version: {self.artifact.version}")
        elif self.name == "image creation":
            print(f"  format: {self.format}")
            print(f"  force: {str(self.force)}")
        elif self.name == "image update":
            print(f"  format: {self.format}")
        elif (
            self.name == 'image build environment creation'
            or self.name == 'image build environment update'
        ):
            print(f"  format: {self.format}")
            print(f"  environment: {self.environment}")
            print(f"  architecture: {self.architecture}")
        elif self.name == "keyring renewal":
            print(f"  duration: {self.duration}")


class WireArtifact(WireData):
    def report(self):
        print(f"- name: {self.name}")
        print(f"  architecture: {self.architecture}")
        print(f"  version: {self.version}")


class WireChangelogEntry(WireData):
    pass


class WireTaskIO(WireData):
    pass


class WireKeyring(WireData):
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
