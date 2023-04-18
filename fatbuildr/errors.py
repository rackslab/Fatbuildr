#!/usr/bin/env python3
#
# Copyright (C) 2023 Rackslab
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


class FatbuildrRuntimeError(Exception):
    pass


class FatbuildrServerError(Exception):
    pass


class FatbuildrServerPermissionError(FatbuildrServerError):
    pass


class FatbuildrPipelineError(Exception):
    pass


class FatbuildrRegistryError(Exception):
    pass


class FatbuildrTokenError(Exception):
    pass


class FatbuildrArtifactError(Exception):
    pass
