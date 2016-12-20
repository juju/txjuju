# Copyright 2016 Canonical Limited.  All rights reserved.

import os
import os.path
import shutil
import tempfile
import unittest

from txjuju._utils import ExecutableNotFoundError, Executable


class ExecutableTests(unittest.TestCase):

    def setUp(self):
        super(ExecutableTests, self).setUp()
        self.dirname = None

    def tearDown(self):
        if self.dirname is not None:
            shutil.rmtree(self.dirname)
        super(ExecutableTests, self).tearDown()

    def _resolve_executable(self, filename):
        if self.dirname is None:
            self.dirname = tempfile.mkdtemp(prefix="txjuju-test-")
        return os.path.join(self.dirname, filename)

    def _write_executable(self, filename):
        filename = self._resolve_executable(filename)
        with open(filename, "w") as file:
            file.write("#!/bin/bash\necho $@\nenv")
        os.chmod(filename, 0o755)
        return filename

    def test_find_exists(self):
        """
        Executable.find() works if the executable exists.
        """
        exe = Executable.find("python2")

        self.assertEqual(exe.filename, "/usr/bin/python2")
        self.assertIsNone(exe.envvars)

    def test_find_does_not_exist(self):
        """
        Executable.find() fails if the executable does not exist.
        """
        filename = self._resolve_executable("does-not-exist")
        with self.assertRaises(ExecutableNotFoundError):
            Executable.find(filename)

    def test_full(self):
        """
        Executable() works when provided all arguments.
        """
        exe = Executable("/usr/local/bin/my-exe", {"SPAM": "eggs"})

        self.assertEqual(exe.filename, "/usr/local/bin/my-exe")
        self.assertEqual(exe.envvars, {"SPAM": "eggs"})

    def test_minimal(self):
        """
        Executable() works with minimal arguments.
        """
        exe = Executable("/usr/local/bin/my-exe")

        self.assertEqual(exe.filename, "/usr/local/bin/my-exe")
        self.assertIsNone(exe.envvars)

    def test_conversion(self):
        """
        Executable() converts the args to str.
        """
        exe = Executable(
            u"/usr/local/bin/my-exe", [(u"SPAM", u"eggs"), ("ham", "")])

        self.assertEqual(exe.filename, "/usr/local/bin/my-exe")
        self.assertEqual(exe.envvars, {"SPAM": "eggs"})

    def test_missing_filename(self):
        """
        Executable() fails if filename is None or empty.
        """
        with self.assertRaises(ValueError):
            Executable(None)
        with self.assertRaises(ValueError):
            Executable("")

    def test_envvars(self):
        """
        Executable.envvars gives a copy of the originally provided env vars.
        """
        exe = Executable("/usr/local/bin/my-exe", {"SPAM": "eggs"})
        exe.envvars["SPAM"] = "ham"

        self.assertEqual(exe.envvars, {"SPAM": "eggs"})

    def test_resolve_args(self):
        """
        Executable.resolve_args() returns the args list that may
        be passed to subprocess.*().
        """
        exe = Executable("/usr/local/bin/my-exe", {"SPAM": "eggs"})
        args = exe.resolve_args("x", "-y", "z")

        self.assertEqual(args, ["/usr/local/bin/my-exe", "x", "-y", "z"])

    def test_run(self):
        """
        Executable.run() runs the command and returns nothing.
        """
        filename = self._write_executable("script")
        exe = Executable(filename, {"SPAM": "eggs"})
        with tempfile.NamedTemporaryFile() as outfile:
            exe.run("x", "-y", "z", stdout=outfile)
            outfile.seek(0)
            out = outfile.read()

        self.assertTrue(out.startswith("x -y z\n"))
        self.assertIn("SPAM=eggs\n", out)

    def test_run_out(self):
        """
        Executable.run_out() runs the command and returns stdout.
        """
        filename = self._write_executable("script")
        self.assertTrue(os.path.exists(filename))
        exe = Executable(filename, {"SPAM": "eggs"})
        out = exe.run_out("x", "-y", "z")

        self.assertTrue(out.startswith("x -y z\n"))
        self.assertIn("SPAM=eggs\n", out)
