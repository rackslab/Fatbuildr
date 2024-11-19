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

import jinja2

from .log import logr

logger = logr(__name__)

#
# Custom Jinja2 filters
#


def filter_gittag(value):
    """Filter to replace characters not authorized in Git tags. This can be
    especially usefull for versions numbers in tarballs URL when the URL is
    composed of the Git tag."""
    return value.replace('~', '-')

def filter_rpm_version(value):
    """Filter to replace characters not authorized in RPM version."""
    return value.replace('-', '~')

def timestamp_rpmdate(value):
    """Filter to convert timestamp to date formatted for RPM spec file changelog
    entries."""
    return datetime.fromtimestamp(value).strftime("%a %b %d %Y")


def timestamp_iso(value):
    """Filter to convert timestamp to date formatted in ISO format."""
    return datetime.fromtimestamp(value).isoformat(sep=' ', timespec='seconds')


def register_filters(env):
    env.filters['gittag'] = filter_gittag
    env.filters['rpm_version'] = filter_rpm_version
    env.filters['timestamp_rpmdate'] = timestamp_rpmdate
    env.filters['timestamp_iso'] = timestamp_iso


class Templeter:
    """Class to abstract backend templating library."""

    def __init__(self):
        # Enable trim_blocks and lstrip_blocks in template as it is easier to
        # add spaces (or disable them occasionnaly in templates) than removing
        # them, and it is usually the expected behaviour with templates blocks.
        # Also keep trailing newline in EOF to avoid breaking prompt with cat.
        self.env = jinja2.Environment(
            trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True
        )
        register_filters(self.env)

    def srender(self, str, **kwargs):
        """Render a string template."""
        try:
            return self.env.from_string(str).render(kwargs)
        except jinja2.exceptions.TemplateSyntaxError as err:
            raise RuntimeError(f"Unable to render template string {str}: {err}")

    def frender(self, path, **kwargs):
        """Render a file template."""
        self.env.loader = jinja2.FileSystemLoader(path.parent)
        try:
            return self.env.get_template(path.name).render(kwargs)
        except jinja2.exceptions.TemplateSyntaxError as err:
            raise RuntimeError(f"Unable to render template file {path}: {err}")
