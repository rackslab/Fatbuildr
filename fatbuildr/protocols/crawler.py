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
from ..builds import ArtifactSourceArchive, ArtifactBuild
from ..builds.factory import BuildFactory
from ..tasks.registry import RegistryArtifactDeletionTask
from ..tasks.keyring import KeyringCreationTask, KeyringRenewalTask
from ..tasks.images import (
    ImageCreationTask,
    ImageUpdateTask,
    ImageShellTask,
    ImageEnvironmentCreationTask,
    ImageEnvironmentUpdateTask,
    ImageEnvironmentShellTask,
)

# types
from ..instances import RunningInstance
from ..registry.formats import RegistryArtifact, ChangelogEntry
from ..keyring import KeyringMasterKey, KeyringSubKey
from ..tasks import TaskIO, TaskJournal


def register_protocols():
    """Load all tasks specific protocol structures in protocol registry."""
    registry = ProtocolRegistry()
    for task in [
        (ArtifactBuild, BuildFactory.generate),
        (RegistryArtifactDeletionTask,),
        (KeyringCreationTask,),
        (KeyringRenewalTask,),
        (ImageCreationTask,),
        (ImageUpdateTask,),
        (ImageShellTask,),
        (ImageEnvironmentCreationTask,),
        (ImageEnvironmentUpdateTask,),
        (ImageEnvironmentShellTask,),
    ]:
        registry.register_task(*task)
    for _type in [
        RunningInstance,
        ArtifactSourceArchive,
        RegistryArtifact,
        ChangelogEntry,
        KeyringMasterKey,
        KeyringSubKey,
        TaskIO,
        TaskJournal,
    ]:
        registry.register_type(_type)
