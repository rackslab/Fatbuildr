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
import tempfile
from pathlib import Path
import shutil

from fatbuildr.git import PatchesDir, PatchesSubdir, PatchFile

class TestPatchesDir(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.patchesdir = PatchesDir(Path(self.test_dir), "1.0.0")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_empty(self):
        # Check initially empty
        self.assertTrue(self.patchesdir.empty)

        # Create one subdir and an empty patch
        subdir = self.patchesdir.version_subdir
        subdir.ensure()
        with open(subdir._path.joinpath("test.path"), "w+"):
            pass

        # Check empty is now false
        self.assertFalse(self.patchesdir.empty)

    def test_path(self):
        self.assertEqual(str(self.patchesdir._path), f"{self.test_dir}/patches")

    def test_version_subdir(self):
        subdir = self.patchesdir.version_subdir
        self.assertEqual(str(subdir._path), f"{self.test_dir}/patches/1.0.0")

    def test_generic_subdir(self):
        subdir = self.patchesdir.generic_subdir
        self.assertEqual(str(subdir._path), f"{self.test_dir}/patches/generic")

    def test_subdirs(self):
        (generic_subdir, version_subdir) = self.patchesdir.subdirs
        self.assertEqual(generic_subdir, self.patchesdir.generic_subdir)
        self.assertEqual(version_subdir, self.patchesdir.version_subdir)

class TestPatchesSubdir(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.patches_dir = PatchesDir(Path(self.test_dir), "1.0.0")
        self.patches_subdir = PatchesSubdir(self.patches_dir, "generic")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_patches(self):
        self.patches_subdir.ensure()
        self.assertCountEqual(self.patches_subdir.patches, [])
        with open(self.patches_subdir._path.joinpath("test.patch"), "w+"):
            pass
        self.assertEqual(len(self.patches_subdir.patches), 1)
        self.assertIsInstance(self.patches_subdir.patches[0], PatchFile)
        self.patches_subdir.clean()
        self.assertCountEqual(self.patches_subdir.patches, [])

    def test_exists(self):
        self.assertFalse(self.patches_subdir.exists())
        self.patches_subdir.ensure()
        self.assertTrue(self.patches_subdir.exists())
