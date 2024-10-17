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
import textwrap

import deb822

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

class TestPatchFile(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.patchesdir = PatchesDir(Path(self.test_dir), "1.0.0")
        (self.generic_subdir, self.version_subdir) = self.patchesdir.subdirs
        # Version specific patch
        self.path = self.version_subdir._path.joinpath("0000-test.patch")
        self.content = textwrap.dedent(
            """
            Description: Very very long multi-line
             description.
            Author: John Doe <john.doe@corp.org>
            Last-Update: 1970-01-02
            """
        )
        self.diff = textwrap.dedent(
            """
            diff --git a/source.py b/source.py
            index 3b1399e..84699ca 100644
            --- a/source.py
            +++ b/source.py
            @@ -1 +1 @@
            -BUG
            +FIX
            """
        )
        self.version_subdir.ensure()
        with open(self.path, "w+") as fh:
            fh.write(self.content + "\n\n" + self.diff)
        self.patch = PatchFile(self.path)

        # Generic subdir
        self.template_path = self.generic_subdir._path.joinpath(
            "0001-template.patch"
        )
        self.template_content = textwrap.dedent(
            """
            Description: Template path.
            Author: John Doe <john.doe@corp.org>
            Last-Update: 1970-01-03
            Template: yes
            """
        )
        self.template_diff = textwrap.dedent(
            """
            diff --git a/source.py b/source.py
            index 3b1399e..84699ca 100644
            --- a/source.py
            +++ b/source.py
            @@ -1 +1 @@
            -BUG
            +{{ version }}
            """
        )
        self.generic_subdir.ensure()
        with open(self.template_path, "w+") as fh:
            fh.write(self.template_content + "\n\n" + self.template_diff)
        self.template_patch = PatchFile(self.template_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_name(self):
        self.assertEqual(self.patch.name, "0000-test.patch")
        self.assertEqual(self.template_patch.name, "0001-template.patch")

    def test_fullname(self):
        self.assertEqual(self.patch.fullname, "1.0.0/0000-test.patch")
        self.assertEqual(
            self.template_patch.fullname, "generic/0001-template.patch"
        )

    def test_content(self):
        self.assertEqual(
            self.patch.content, (self.content + "\n\n" + self.diff).encode()
        )

    def test_title(self):
        self.assertEqual(self.patch.title, "test.patch")
        self.assertEqual(self.template_patch.title, "template.patch")

    def test_meta(self):
        self.assertEqual(
            self.patch.meta["Description"],
            "Very very long multi-line\n description."
        )
        self.assertEqual(
            self.patch.meta["Author"], "John Doe <john.doe@corp.org>"
        )
        self.assertEqual(
            self.patch.meta["Last-Update"], "1970-01-02"
        )
        # Test undefined key
        self.assertNotIn("Unknown", self.patch.meta)
        with self.assertRaises(KeyError):
            self.patch.meta["Unknown"]

    def test_template(self):
        self.assertFalse(self.patch.template)
        self.assertTrue(self.template_patch.template)

    def render(self):
        self.template_patch.render(version="3.2.1")
        self.assertTrue(
            self.template_patch.content().decode().endswith("3.2.1\n")
        )

    def test_in_field(self):
        self.assertTrue(self.patch.in_field("Author", "John"))
        self.assertFalse(self.patch.in_field("Description", "short"))
        with self.assertRaises(KeyError):
            self.patch.in_field("Unknown", "whatever")

    def test_generic(self):
        self.assertFalse(self.patch.generic)
        self.assertTrue(self.template_patch.generic)

    def test_create(self):
        patch = PatchFile.create(self.generic_subdir, "0002-creation-test")
        self.assertIsInstance(patch, PatchFile)
        self.assertEqual(patch.title, "creation-test")

    def test_write(self):
        meta = deb822.Deb822()
        meta["Author"] = "Jane Doe <jane.doe@corp.org>"
        self.patch.write(meta, self.diff)
        self.assertEqual(
            self.patch.meta["Author"],
            "Jane Doe <jane.doe@corp.org>"
        )

    def test_rename(self):
        to = self.generic_subdir._path.joinpath("0002-renamed.patch")
        self.patch.rename(to)
        self.assertTrue(to.exists())

    def test_remove(self):
        self.patch.remove()
        self.assertFalse(self.path.exists())
