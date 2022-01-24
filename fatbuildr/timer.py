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

import threading
from datetime import datetime

from .log import logr

logger = logr(__name__)


class ServerTimer:
    def __init__(self, timeout=30):
        self.start = datetime.now().timestamp()
        self.timeout = timeout
        self.event = threading.Event()
        self._lock = threading.Lock()

    def reset(self):
        logger.debug("Reseting timer")
        self.start = datetime.now().timestamp()

    @property
    def remaining(self):
        return max(0, (self.start + self.timeout) - datetime.now().timestamp())

    @property
    def over(self):
        return not self._lock.locked() and self.remaining == 0

    def lock(self):
        if not self._lock.locked():
            self._lock.acquire()

    def release(self):
        if self._lock.locked():
            self._lock.release()

    def wait(self, timeout):
        logger.debug("Waiting for timer lock for %f seconds" % (timeout))
        acquired = self._lock.acquire(timeout=timeout)
        if acquired:
            self._lock.release()  # release is instantly
            if self.remaining:
                logger.debug("Waiting for %f seconds" % (self.remaining))
                self.event.wait(timeout=self.remaining)
