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

from ..protocols.exports import ProtocolRegistry

# tasks
from ..builds import ArtefactBuild
from ..builds.factory import BuildFactory
from ..tasks.registry import RegistryArtefactDeletionTask
from ..tasks.keyring import KeyringCreationTask, KeyringRenewalTask
from ..tasks.images import (
    ImageCreationTask,
    ImageUpdateTask,
    ImageEnvironmentCreationTask,
    ImageEnvironmentUpdateTask,
)

# types
from ..instances import RunningInstance
from ..registry.formats import RegistryArtefact, ChangelogEntry
from ..keyring import KeyringMasterKey, KeyringSubKey


def register_protocols():
    """Load all tasks specific protocol structures in protocol registry."""
    registry = ProtocolRegistry()
    for task in [
        (ArtefactBuild, BuildFactory.generate),
        (RegistryArtefactDeletionTask,),
        (KeyringCreationTask,),
        (KeyringRenewalTask,),
        (ImageCreationTask,),
        (ImageUpdateTask,),
        (ImageEnvironmentCreationTask,),
        (ImageEnvironmentUpdateTask,),
    ]:
        registry.register_task(*task)
    for _type in [
        RunningInstance,
        RegistryArtefact,
        ChangelogEntry,
        KeyringMasterKey,
        KeyringSubKey,
    ]:
        registry.register_type(_type)
