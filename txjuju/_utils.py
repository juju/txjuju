# Copyright 2016 Canonical Limited.  All rights reserved.

import subprocess
from collections import namedtuple

import yaml


class Executable(namedtuple("Executable", "filename envvars")):
    """A single executable."""

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
        args = self.resolve_args(*args)
        subprocess.check_call(args, env=self.envvars, **kwargs)

    def run_out(self, *args, **kwargs):
        """Return the output from running the executable with the given args.

        The provided kwargs are those that subprocess.* supports.
        """
        args = self.resolve_args(*args)
        return subprocess.check_output(args, env=self.envvars, **kwargs)


class UnicodeYamlLoader(yaml.Loader):
    """yaml loader class returning unicode objects instead of python str."""
UnicodeYamlLoader.add_constructor(
    u'tag:yaml.org,2002:str', UnicodeYamlLoader.construct_scalar)
