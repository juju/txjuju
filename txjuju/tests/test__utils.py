# Copyright 2016 Canonical Limited.  All rights reserved.

import os
import os.path
import shutil
import tempfile
import unittest

from txjuju._utils import Executable


class ExecutableTests(unittest.TestCase):

    def setUp(self):
        super(ExecutableTests, self).setUp()
        self.dirname = None

    def tearDown(self):
        if self.dirname is not None:
            shutil.rmtree(self.dirname)
        super(ExecutableTests, self).tearDown()

    def _write_executable(self, filename):
        if self.dirname is None:
            self.dirname = tempfile.mkdtemp(prefix="txjuju-test-")
        filename = os.path.join(self.dirname, filename)
        with open(filename, "w") as file:
            file.write("#!/bin/bash\necho $@\nenv")
        os.chmod(filename, 0o755)
        return filename

    def test_full(self):
        exe = Executable("my-exe", {"SPAM": "eggs"})

        self.assertEqual(exe.filename, "my-exe")
        self.assertEqual(exe.envvars, {"SPAM": "eggs"})

    def test_minimal(self):
        exe = Executable("my-exe")

        self.assertEqual(exe.filename, "my-exe")
        self.assertIsNone(exe.envvars)

    def test_conversion(self):
        exe = Executable(u"my-exe", [(u"SPAM", u"eggs"), ("ham", "")])

        self.assertEqual(exe.filename, "my-exe")
        self.assertEqual(exe.envvars, {"SPAM": "eggs"})

    def test_missing_filename(self):
        with self.assertRaises(ValueError):
            Executable(None)
        with self.assertRaises(ValueError):
            Executable("")

    def test_envvars(self):
        exe = Executable("my-exe", {"SPAM": "eggs"})
        exe.envvars["SPAM"] = "ham"

        self.assertEqual(exe.envvars, {"SPAM": "eggs"})

    def test_resolve_args(self):
        exe = Executable("my-exe", {"SPAM": "eggs"})
        args = exe.resolve_args("x", "-y", "z")

        self.assertEqual(args, ["my-exe", "x", "-y", "z"])

    def test_run(self):
        filename = self._write_executable("script")
        exe = Executable(filename, {"SPAM": "eggs"})
        with tempfile.NamedTemporaryFile() as outfile:
            exe.run("x", "-y", "z", stdout=outfile)
            outfile.seek(0)
            out = outfile.read()

        self.assertTrue(out.startswith("x -y z\n"))
        self.assertIn("SPAM=eggs\n", out)

    def test_run_out(self):
        filename = self._write_executable("script")
        self.assertTrue(os.path.exists(filename))
        exe = Executable(filename, {"SPAM": "eggs"})
        out = exe.run_out("x", "-y", "z")

        self.assertTrue(out.startswith("x -y z\n"))
        self.assertIn("SPAM=eggs\n", out)
