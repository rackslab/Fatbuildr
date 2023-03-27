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


from . import RunnableTask
from ..protocols.exports import ExportableTaskField
from ..log import logr

logger = logr(__name__)


class ImageCreationTask(RunnableTask):

    TASK_NAME = 'image creation'
    EXFIELDS = {
        ExportableTaskField('format'),
        ExportableTaskField('force', bool),
    }

    def __init__(self, task_id, user, place, instance, format, force):
        super().__init__(task_id, user, place, instance)
        self.format = format
        self.force = force

    def run(self):
        logger.info(
            "Running image creation task %s",
            self.id,
        )
        self.instance.images_mgr.prepare()
        img = self.instance.images_mgr.image(self.format)
        img.create(self, self.force)


class ImageUpdateTask(RunnableTask):

    TASK_NAME = 'image update'
    EXFIELDS = {
        ExportableTaskField('format'),
    }

    def __init__(self, task_id, user, place, instance, format):
        super().__init__(task_id, user, place, instance)
        self.format = format

    def run(self):
        logger.info(
            "Running image update task %s",
            self.id,
        )
        img = self.instance.images_mgr.image(self.format)
        img.update(self)


class ImageShellTask(RunnableTask):

    TASK_NAME = 'image shell'
    EXFIELDS = {
        ExportableTaskField('format'),
        ExportableTaskField('term'),
    }

    def __init__(self, task_id, user, place, instance, format, term):
        super().__init__(task_id, user, place, instance, interactive=True)
        self.format = format
        self.term = term

    def run(self):
        logger.info(
            "Running image shell task %s",
            self.id,
        )
        img = self.instance.images_mgr.image(self.format)
        img.shell(self, self.term)


class ImageEnvironmentCreationTask(RunnableTask):

    TASK_NAME = 'image build environment creation'
    EXFIELDS = {
        ExportableTaskField('format'),
        ExportableTaskField('environment'),
        ExportableTaskField('architecture'),
    }

    def __init__(
        self, task_id, user, place, instance, format, environment, architecture
    ):
        super().__init__(task_id, user, place, instance)
        self.format = format
        self.environment = environment
        self.architecture = architecture

    def run(self):
        logger.info(
            "Running image build environment creation task %s",
            self.id,
        )
        build_env = self.instance.images_mgr.build_env(
            self.format, self.environment, self.architecture
        )
        build_env.create(self)


class ImageEnvironmentUpdateTask(RunnableTask):

    TASK_NAME = 'image build environment update'
    EXFIELDS = {
        ExportableTaskField('format'),
        ExportableTaskField('environment'),
        ExportableTaskField('architecture'),
    }

    def __init__(
        self, task_id, user, place, instance, format, environment, architecture
    ):
        super().__init__(task_id, user, place, instance)
        self.format = format
        self.environment = environment
        self.architecture = architecture

    def run(self):
        logger.info(
            "Running image build environment update task %s",
            self.id,
        )
        build_env = self.instance.images_mgr.build_env(
            self.format, self.environment, self.architecture
        )
        build_env.update(self)


class ImageEnvironmentShellTask(RunnableTask):

    TASK_NAME = 'image build environment shell'
    EXFIELDS = {
        ExportableTaskField('format'),
        ExportableTaskField('environment'),
        ExportableTaskField('architecture'),
        ExportableTaskField('term'),
    }

    def __init__(
        self,
        task_id,
        user,
        place,
        instance,
        format,
        environment,
        architecture,
        term,
    ):
        super().__init__(task_id, user, place, instance, interactive=True)
        self.format = format
        self.environment = environment
        self.architecture = architecture
        self.term = term

    def run(self):
        logger.info(
            "Running image build environment shell task %s",
            self.id,
        )
        build_env = self.instance.images_mgr.build_env(
            self.format, self.environment, self.architecture
        )
        build_env.shell(self, self.term)
