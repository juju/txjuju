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
        self.os_env_orig = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.os_env_orig)
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

    def test_find_on_os_environs_PATH(self):
        """
        Executable.find() succeeds if the executable exists and
        is located under os.environ["PATH"]
        """
        filename = self._write_executable("script")
        os.environ["PATH"] = os.path.dirname(filename)
        exe = Executable.find("script")

        self.assertEqual(exe.filename, filename)
        self.assertIsNone(exe.envvars)

    def test_find_does_not_exist(self):
        """
        Executable.find() fails if the executable does not exist,
        even if an absolute filename is provided (an absolute filename
        makes $PATH irrelevant).
        """
        filename = self._resolve_executable("does-not-exist")

        with self.assertRaises(ExecutableNotFoundError):
            Executable.find(filename)

    def test_find_not_on_PATH_relative(self):
        """
        Executable.find() fails if the executable is not under $PATH.
        """
        filename = self._write_executable("script")
        os.environ["PATH"] = "/not/the/dir/we/want"

        with self.assertRaises(ExecutableNotFoundError):
            Executable.find("script")

    def test_find_not_on_PATH_absolute(self):
        """
        Executable.find() succeeds if unfindable but absolute filename.
        """
        filename = self._write_executable("script")
        os.environ["PATH"] = "/dir/does/not/exist"
        exe = Executable.find(filename)

        self.assertEqual(exe.filename, filename)

    def test_find_on_envvars_PATH(self):
        """
        Executable.find() succeeds if envvars has $PATH set and the
        executable is locatd under it.  os.environ["PATH"] is ignored.
        """
        filename = self._write_executable("script")
        os.environ["PATH"] = "/not/the/dir/we/want"
        envvars = {
                "PATH": self.dirname,
                "SPAM": "eggs",
                }
        exe = Executable.find("script", envvars)

        self.assertEqual(exe.filename, filename)
        self.assertEqual(exe.envvars, envvars)

    def test_find_not_on_envvars_PATH(self):
        """
        Executable.find() fails for a relative filename if envvars
        is provided and has $PATH set, but the executable is not
        located under it, even if it *is* findable under
        os.environ["PATH"].
        """
        filename = self._write_executable("script")
        os.environ["PATH"] = os.path.dirname(filename)
        envvars = {
                "PATH": "/not/the/dir/we/want",
                "SPAM": "eggs",
                }

        with self.assertRaises(ExecutableNotFoundError):
            Executable.find("script", envvars)

    def test_find_no_envvars_PATH_but_on_os_environs_PATH(self):
        """
        Executable.find() succeeds if the provided envvars does not
        have $PATH set, but os.environ does and the executable is
        located under it.
        """
        filename = self._write_executable("script")
        os.environ["PATH"] = os.path.dirname(filename)
        envvars = {
                "SPAM": "eggs",
                }
        exe = Executable.find("script", envvars)

        self.assertEqual(exe.filename, filename)
        self.assertEqual(exe.envvars, envvars)

    def test_find_no_envvars_PATH_not_on_os_environs_PATH_relative(self):
        """
        Executable.find() fails if the filename is relative and
        the executable is not found under $PATH in envvars nor in
        os.environ.
        """
        filename = self._write_executable("script")
        os.environ["PATH"] = "/not/the/dir/we/want"
        envvars = {
                "SPAM": "eggs",
                }

        with self.assertRaises(ExecutableNotFoundError):
            Executable.find("script", envvars)

    def test_find_no_envvars_PATH_not_on_os_environs_PATH_absolute(self):
        """
        Executable.find() succeeds if the filename is absolute, even
        if envars is provided without $PATH and the executable is not
        located under os.environ["PATH"].
        """
        filename = self._write_executable("script")
        os.environ["PATH"] = "/not/the/dir/we/want"
        envvars = {
                "SPAM": "eggs",
                }
        exe = Executable.find(filename, envvars)

        self.assertEqual(exe.filename, filename)
        self.assertEqual(exe.envvars, envvars)

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

    def test_relative_filename(self):
        """
        Executable() fails if filename is None or empty.
        """
        with self.assertRaises(ValueError):
            Executable("x/y/z")

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

    def test_run_exists(self):
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

    def test_run_executable_does_not_exist(self):
        """
        Executable.run() fails if the executable does not exist.
        """
        filename = self._resolve_executable("does-not-exist")
        exe = Executable(filename)

        with self.assertRaises(ExecutableNotFoundError):
            exe.run()

    def test_run_out_exists(self):
        """
        Executable.run_out() runs the command and returns stdout.
        """
        filename = self._write_executable("script")
        self.assertTrue(os.path.exists(filename))
        exe = Executable(filename, {"SPAM": "eggs"})
        out = exe.run_out("x", "-y", "z")

        self.assertTrue(out.startswith("x -y z\n"))
        self.assertIn("SPAM=eggs\n", out)

    def test_run_executable_does_not_exist(self):
        """
        Executable.run_out() fails if the executable does not exist.
        """
        filename = self._resolve_executable("does-not-exist")
        exe = Executable(filename)

        with self.assertRaises(ExecutableNotFoundError):
            exe.run_out()
