#!/usr/bin/env python3
#
# Copyright (C) 2024 Rackslab
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

import unittest
import textwrap
from datetime import datetime

from fatbuildr.templates import Templeter


class TestTempleter(unittest.TestCase):
    def setUp(self):
        self.templeter = Templeter()

    def test_srender(self):
        self.assertEqual(
            self.templeter.srender(
                textwrap.dedent(
                    """
                    text
                    {{ key }} = {{ value }}
                    """
                ),
                key="test",
                value="running",
            ),
            textwrap.dedent(
                """
                text
                test = running
                """
            ),
        )

    def test_filter_gittag(self):
        self.assertEqual(
            self.templeter.srender(
                "{{ version | gittag }}", version="1.2-0~rc1"
            ),
            "1.2-0-rc1",
        )

    def test_filter_timestamp_rpmdate(self):
        self.assertEqual(
            self.templeter.srender(
                "{{ timestamp | timestamp_rpmdate }}",
                timestamp=datetime.timestamp(datetime(2000, 2, 3)),
            ),
            "Thu Feb 03 2000",
        )

    def test_filter_timestamp_iso(self):
        self.assertEqual(
            self.templeter.srender(
                "{{ timestamp | timestamp_iso }}",
                timestamp=datetime.timestamp(datetime(2000, 2, 3, 4, 5, 6)),
            ),
            "2000-02-03 04:05:06",
        )
