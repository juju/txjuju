# Copyright 2016 Canonical Limited.  All rights reserved.

import json
import os
import os.path
import subprocess

from testtools.content import content_from_file

from fixtures import Fixture, TempDir, EnvironmentVariable


FAKE_JUJU_VERSION = "1.25.6"
FAKE_JUJU_BINARY = "/usr/bin/fake-juju-%s" % FAKE_JUJU_VERSION
FAKE_JUJU_ENVIRONMENTS_YAML = """environments:
    test:
        admin-secret: test
        default-series: trusty
        type: dummy
"""


class FakeJujuFixture(Fixture):
    """Manages a fake-juju process."""

    def __init__(self, logs_dir=None):
        """
        @param logs_dir: If given, copy logs to this directory upon cleanup,
            otherwise, print it as test plain text detail upon failure.
        """
        self._logs_dir = logs_dir

    def setUp(self):
        super(FakeJujuFixture, self).setUp()
        self._juju_home = self.useFixture(TempDir())
        if self._logs_dir:
            # If we are given a logs dir, dump logs there
            self.useFixture(EnvironmentVariable(
                "FAKE_JUJU_LOGS_DIR", self._logs_dir))
        else:
            # Otherwise just attatch them as testtools details
            self.addDetail(
                "log-file", content_from_file(self._fake_juju_log))
        api_info = bootstrap_fake_juju(self._juju_home.path)
        self.uuid = api_info["environ-uuid"]
        self.address = api_info["state-servers"][0]

    def cleanUp(self):
        destroy_fake_juju(self._juju_home.path)
        super(FakeJujuFixture, self).cleanUp()

    def add_failure(self, entity):
        """Make the given entity fail with an error status."""
        add_fake_juju_failure(self._juju_home.path, entity)

    @property
    def _fake_juju_log(self):
        """Return the path to the fake-juju log file."""
        return self._juju_home.join("fake-juju.log")


def bootstrap_fake_juju(juju_home_path):
    """Bootstrap a fake-juju environment and return its info."""
    with open(os.path.join(juju_home_path, "environments.yaml"), "w") as fd:
        fd.write(FAKE_JUJU_ENVIRONMENTS_YAML)
    env = os.environ.copy()
    env.update({
        "JUJU_HOME": juju_home_path,
        "FAKE_JUJU_FAILURES": get_fake_juju_failures_path(juju_home_path),
    })
    subprocess.check_output([FAKE_JUJU_BINARY, "bootstrap"], env=env)
    output = subprocess.check_output([FAKE_JUJU_BINARY, "api-info"], env=env)
    return json.loads(output)


def destroy_fake_juju(juju_home_path):
    """Destroy a fake-juju environment."""
    env = os.environ.copy()
    env["JUJU_HOME"] = juju_home_path
    subprocess.check_output([FAKE_JUJU_BINARY, "destroy-environment"], env=env)


def add_fake_juju_failure(juju_home_path, entity):
    """Make the given entity fail with an error status."""
    with open(get_fake_juju_failures_path(juju_home_path), "a") as fd:
        fd.write("{}\n".format(entity))


def clean_fake_juju_failure(juju_home_path):
    """Remove the juju-failures file, if found."""
    path = get_fake_juju_failures_path(juju_home_path)
    if os.path.exists(path):
        os.unlink(path)


def get_fake_juju_failures_path(juju_home_path):
    """Return the path of the juju-failures file in the given Juju home dir."""
    return os.path.join(juju_home_path, "juju-failures")
