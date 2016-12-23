# Copyright 2016 Canonical Limited.  All rights reserved.

import os
import os.path
import subprocess
from collections import namedtuple
from distutils.spawn import find_executable

import yaml


class ExecutableNotFoundError(Exception):
    """An executable was not found."""

    def __init__(self, executable, path):
        msg = "executable {!r} not found".format(executable)
        super(ExecutableNotFoundError, self).__init__(msg)
        self.executable = executable
        self.path = path


class Executable(namedtuple("Executable", "filename envvars")):
    """A single executable."""

    @classmethod
    def find(cls, name, envvars=None):
        """Return the named executable if it exists on the path.

        If it doesn't exist then ExecutableNotFoundError is raised.
        """
        if not name:
            return cls(name, envvars) # This will trigger an exception.

        path = (envvars or os.environ).get("PATH")
        found = find_executable(name, path)
        if found == None:
            raise ExecutableNotFoundError(name, path)
        return cls(found, envvars)

    def __new__(cls, filename, envvars=None):
        """
        @param filename: The path to the executable file.
        @param envvars: The environment variables with which
            to run the executable.
        """
        filename = str(filename) if filename else None
        if envvars is not None:
            if not hasattr(envvars, "items"):
                envvars = dict(envvars)
            envvars = {str(k): str(v) for k, v in envvars.items() if v}
        return super(Executable, cls).__new__(cls, filename, envvars)

    def __init__(self, *args, **kwargs):
        if not self.filename:
            raise ValueError("missing filename")
        if not os.path.isabs(self.filename):
            raise ValueError("filename must be an absolute path")

    @property
    def envvars(self):
        """The environment variables used when running the executable."""
        envvars = super(Executable, self).envvars
        if envvars is None:
            return None
        return dict(envvars)

    def resolve_args(self, *args):
        """Return the full args to pass to subprocess.*."""
        return [self.filename] + list(args)

    def run(self, *args, **kwargs):
        """Run the executable with the given args.

        The provided kwargs are those that subprocess.* supports.
        """
        call = subprocess.check_call
        self._run(call, *args, **kwargs)

    def run_out(self, *args, **kwargs):
        """Return the output from running the executable with the given args.

        The provided kwargs are those that subprocess.* supports.
        """
        call = subprocess.check_output
        return self._run(call, *args, **kwargs)

    def _run(self, call, *args, **kwargs):
        args = self.resolve_args(*args)
        envvars = self.envvars
        try:
            return call(args, env=envvars, **kwargs)
        except Exception:
            path = envvars["PATH"] if envvars else None
            try:
                found = find_executable(self.filename, path)
            except Exception:
                pass  # Defer to the original exception.
            else:
                if found == None:
                    raise ExecutableNotFoundError(self.filename, path)
            raise


class UnicodeYamlLoader(yaml.Loader):
    """yaml loader class returning unicode objects instead of python str."""
UnicodeYamlLoader.add_constructor(
    u'tag:yaml.org,2002:str', UnicodeYamlLoader.construct_scalar)
