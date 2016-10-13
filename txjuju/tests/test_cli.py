# Copyright 2016 Canonical Limited.  All rights reserved.

from collections import namedtuple
import json
import os
import unittest

import yaml
from mocker import MockerTestCase
from twisted.internet.defer import inlineCallbacks

from txjuju import config, _utils
from txjuju.cli import (
    Juju1CLI, Juju2CLI, BootstrapSpec, APIInfo, get_executable)
from txjuju.errors import CLIError
from txjuju.testing import TwistedTestCase


class GetExecutableTest(unittest.TestCase):

    class CLI(object):
        CFGDIR_ENVVAR = "JUJU_HOME"

    def test_full(self):
        """
        get_executable() works when all args are provided.
        """
        exe = get_executable("spam", self.CLI, "/tmp", {"SPAM": "eggs"})

        self.assertEqual(
            exe,
            _utils.Executable("spam", {"SPAM": "eggs", "JUJU_HOME": "/tmp"}))

    def test_minimal(self):
        """
        get_executable() works when given minimal args.
        """
        exe = get_executable("spam", self.CLI, "/tmp")

        self.assertEqual(exe.filename, "spam")
        self.assertEqual(exe.envvars["JUJU_HOME"], "/tmp")
        self.assertNotEqual(exe.envvars, {"JUJU_HOME": "/tmp"})

    def test_missing_filename(self):
        """
        get_executable() fails if filename is None or empty.
        """
        with self.assertRaises(ValueError):
            get_executable("", self.CLI, "/tmp")
        with self.assertRaises(ValueError):
            get_executable(None, self.CLI, "/tmp")

    def test_missing_version_cli(self):
        """
        get_executable() fails if version_cli is None.
        """
        with self.assertRaises(ValueError):
            get_executable("spam", None, "/tmp")

    def test_missing_cfgdir(self):
        """
        get_executable() fails if cfgdir is None or empty.
        """
        with self.assertRaises(ValueError):
            get_executable("spam", self.CLI, None)
        with self.assertRaises(ValueError):
            get_executable("spam", self.CLI, "")


class BootstrapSpecTest(unittest.TestCase):

    def test_full(self):
        """
        BootstrapSpec() works when all args are provided.
        """
        spec = BootstrapSpec("my-env", "lxd", "xenial", "pw")

        self.assertEqual(spec.name, "my-env")
        self.assertEqual(spec.driver, "lxd")
        self.assertEqual(spec.default_series, "xenial")
        self.assertEqual(spec.admin_secret, "pw")

    def test_minimal(self):
        """
        BootstrapSpec() works with minimal args.
        """
        spec = BootstrapSpec("my-env", "lxd")

        self.assertEqual(spec.name, "my-env")
        self.assertEqual(spec.driver, "lxd")
        self.assertEqual(spec.default_series, "trusty")
        self.assertIsNone(spec.admin_secret)

    def test_repr_full(self):
        """
        The repr of BootstrapSpec is correct.
        """
        spec = BootstrapSpec("my-env", "lxd", "xenial", "pw")
        self.assertEqual(
            repr(spec),
            ("BootstrapSpec(name='my-env', driver='lxd', "
             "default_series='xenial', admin_secret='pw')"),
            )

    def test_repr_minimal(self):
        """
        The repr of BootstrapSpec is correct even if some fields are missing.
        """
        spec = BootstrapSpec("my-env", "lxd")
        self.assertEqual(
            repr(spec),
            ("BootstrapSpec(name='my-env', driver='lxd', "
             "default_series='trusty', admin_secret=None)"),
            )

    def test___eq___same_with_base_class(self):
        """
        BootstrapSpec == other is True when they are the same
        and have the same class.
        """
        spec = BootstrapSpec("my-env", "lxd")
        other = BootstrapSpec("my-env", "lxd")

        self.assertTrue(spec == other)

    def test___eq___same_with_sub_class(self):
        """
        BootstrapSpec == other is True when they are the same,
        even if the other is a BootstrapSpec subclass.
        """
        spec = BootstrapSpec("my-env", "lxd")
        other = type("SubSpec", (BootstrapSpec,), {})("my-env", "lxd")

        self.assertTrue(spec == other)

    def test___eq___same_with_other_class(self):
        """
        BootstrapSpec == other is True when they are the same,
        even if the classes are different.
        """
        spec = BootstrapSpec("my-env", "lxd", "trusty", "pw")
        other_cls = namedtuple("Sub",
                               "name driver default_series admin_secret")
        other = other_cls("my-env", "lxd", "trusty", "pw")

        self.assertTrue(spec == other)

    def test___eq___identity(self):
        """
        For BootstrapSpec, spec == spec is True.
        """
        spec = BootstrapSpec("my-env", "lxd")

        self.assertTrue(spec == spec)

    def test___eq___different(self):
        """
        BootstrapSpec == other is False when they differ.
        """
        spec = BootstrapSpec("my-env", "lxd")
        other = BootstrapSpec("my-env", "spam")

        self.assertFalse(spec == other)

    def test___ne___same(self):
        """
        BootstrapSpec != other is False when they are the same.
        """
        spec = BootstrapSpec("my-env", "lxd")
        other = BootstrapSpec("my-env", "lxd")

        self.assertFalse(spec != other)

    def test___ne___different(self):
        """
        BootstrapSpec != other is True when they differ.
        """
        spec = BootstrapSpec("my-env", "lxd")
        other = BootstrapSpec("my-env", "spam")

        self.assertTrue(spec != other)

    def test_config(self):
        """
        BootstrapSpec.config() returns a Config containing
        a ControllerConfig corresponding to the bootstrap spec.
        """
        spec = BootstrapSpec("my-env", "lxd", "xenial", "pw")
        cfg = spec.config()

        self.assertEqual(len(cfg.controllers), 1)
        self.assertEqual(
            cfg.controllers[0],
            config.ControllerConfig(
                "my-env",
                config.CloudConfig("lxd", "lxd"),
                config.BootstrapConfig("xenial", "pw"),
                ),
            )


class APIInfoTest(unittest.TestCase):

    def test_full(self):
        """
        APIInfo() works with all args provided.
        """
        endpoints = (u"host2", u"host1")
        info = APIInfo(endpoints, u"admin", u"pw", u"some-uuid")

        self.assertEqual(info.endpoints, (u"host2", u"host1"))
        self.assertEqual(info.user, u"admin")
        self.assertEqual(info.password, u"pw")
        self.assertEqual(info.model_uuid, u"some-uuid")

    def test_minimal(self):
        """
        APIInfo() works with minimal args.
        """
        endpoints = (u"host",)
        info = APIInfo(endpoints, u"admin", u"pw")

        self.assertEqual(info.endpoints, (u"host",))
        self.assertEqual(info.user, u"admin")
        self.assertEqual(info.password, u"pw")
        self.assertIsNone(info.model_uuid)

    def test_conversion(self):
        """
        APIInfo() converts the args to unicode.
        """
        endpoints = ["host2", "host1"]
        info = APIInfo(endpoints, "admin", "pw", "some-uuid")

        self.assertEqual(info.endpoints, (u"host2", u"host1"))
        self.assertEqual(info.user, u"admin")
        self.assertEqual(info.password, u"pw")
        self.assertEqual(info.model_uuid, u"some-uuid")

    def test_missing_endpoints(self):
        """
        APIInfo() fails if endpoints is None or empty.
        """
        with self.assertRaises(ValueError):
            APIInfo(None, "admin", "pw")
        with self.assertRaises(ValueError):
            APIInfo([], "admin", "pw")

    def test_missing_user(self):
        """
        APIInfo() fails if user is None or empty.
        """
        with self.assertRaises(ValueError):
            APIInfo(["host"], None, "pw")
        with self.assertRaises(ValueError):
            APIInfo(["host"], "", "pw")

    def test_missing_password(self):
        """
        APIInfo() fails if password is None or empty.
        """
        with self.assertRaises(ValueError):
            APIInfo(["host"], "admin", None)
        with self.assertRaises(ValueError):
            APIInfo(["host"], "admin", "")

    def test_address(self):
        """
        APIInfo.address holds the first endpoint.
        """
        info = APIInfo(["host2", "host1"], "admin", "pw")

        self.assertEqual(info.address, "host2")


class Juju1CLITest(TwistedTestCase, MockerTestCase):
    # XXX bug #1558600 to be removed with juju2 feature flag

    def setUp(self):
        super(Juju1CLITest, self).setUp()
        self.juju_home = self.makeDir()
        self.environment_name = "maas_env_name"
        self.bootstrap_machine = "maas-name"
        self.cli = Juju1CLI(self.juju_home)

    def test_juju_home_respected(self):
        """L{JujuCLI} takes a parameter which sets $JUJU_HOME."""
        juju_executable = self.makeFile("#!/bin/sh\necho -n $JUJU_HOME")
        os.chmod(juju_executable, 0755)
        self.assertIs(self.cli.juju_home, self.juju_home)
        self.cli.juju_binary_path = juju_executable

        def callback(result):
            out, err = result
            self.assertEqual(self.juju_home, out)
        deferred = self.cli.bootstrap(
            self.environment_name, self.bootstrap_machine)
        deferred.addCallback(callback)
        return deferred

    def test_juju_bootstrap_calls_bootstrap(self):
        """
        JujuCLI.bootstrap calls juju bootstrap with an C{environment_name}
        and the C{bootstrap_machine} as the --to parameter.
        """
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        def callback(result):
            out, err = result
            self.assertEqual(
                "bootstrap -v -e %s --to %s --no-auto-upgrade" % (
                    self.environment_name, self.bootstrap_machine),
                out)
        deferred = self.cli.bootstrap(
            self.environment_name, self.bootstrap_machine)
        deferred.addCallback(callback)
        return deferred

    def test_auto_upgrades_disabled(self):
        """When bootstrapping, auto-upgrades are disabled."""
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        def callback(result):
            out, err = result
            self.assertIn("--no-auto-upgrade", out)

        deferred = self.cli.bootstrap(
            self.environment_name, self.bootstrap_machine)
        deferred.addCallback(callback)
        return deferred

    def test_wb_juju_api_info_calls_api_info(self):
        """
        JujuCLI.api_info calls juju api-info passing the environment_name
        parameter.
        """
        juju_executable = self.makeFile("#!/bin/sh\necho $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable
        self.cli._parse_json_output = lambda (stdout, stderr): stdout

        def callback(stdout):
            self.assertEqual(
                "api-info -e %s --refresh --format=json\n" %
                self.environment_name,
                stdout)
        deferred = self.cli.api_info(self.environment_name)
        deferred.addCallback(callback)
        return deferred

    def test_juju_api_info(self):
        """JujuCLI.api_info returns API info."""

        info = {
            "ca-cert": "certificate data",
            "environ-uuid": "foo-bar-baz",
            "state-servers": ["1.2.3.4:17070", "5.6.7.8:17070"],
            "user": "admin"}
        juju_executable = self.makeFile(
            "#!/bin/sh\necho '%s'" % json.dumps(info))
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        def callback(result):
            self.assertEqual(info, result)

        deferred = self.cli.api_info(self.environment_name)
        deferred.addCallback(callback)
        return deferred

    def test_juju_bootstrap_non_zero(self):
        """JujuCLI.bootstrap raises CLIError if bootstrap fails."""
        juju_executable = self.makeFile("#!/bin/sh\nexit 1")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        def callback(_):
            [failure] = self.flushLoggedErrors(CLIError)
            self.assertEqual(1, failure.value.code)

        deferred = self.cli.bootstrap(
            self.environment_name, self.bootstrap_machine)
        self.assertFailure(deferred, CLIError)
        deferred.addCallback(callback)
        return deferred

    def test_juju_destroy_environment_calls_destroy_environment(self):
        """
        C{JujuCLI.destroy_environment} calls juju destroy-environment
        with an C{environment_name} and --yes option.
        """
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        def callback((out, err)):
            self.assertEqual(
                'destroy-environment --yes %s' % self.environment_name,
                out)

        deferred = self.cli.destroy_environment(self.environment_name)
        deferred.addCallback(callback)
        return deferred

    def test_juju_destroy_environment_calls_destroy_environment_force(self):
        """
        C{JujuCLI.destroy_environment} calls juju destroy-environment
        with the --force parameter if C{force} is C{True}.
        """
        juju_executable = self.makeFile("#!/bin/sh\n" "echo -n $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        def callback((out, err)):
            self.assertEqual(
                'destroy-environment --yes --force %s' % self.environment_name,
                out)

        deferred = self.cli.destroy_environment(
            self.environment_name, force=True)
        deferred.addCallback(callback)
        return deferred

    def test_get_juju_status(self):
        """
        The C{JujuCLI.get_juju_status} method outputs the current juju
        status to a specified file location.
        """
        juju_executable = self.makeFile("#!/bin/sh\n" "echo -n $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        expected = ("status -e %s -o /tmp/landscape-logs/juju-status.out")

        def callback((out, err)):
            self.assertEqual(
                expected % self.environment_name, out)

        deferred = self.cli.get_juju_status(
            self.environment_name,
            output_file_path="/tmp/landscape-logs/juju-status.out")
        deferred.addCallback(callback)
        return deferred

    def test_fetch_file(self):
        """
        The C{JujuCLI.fetch_remote_file} copies the specified
        file from a juju machine's filesystem to the local one.
        """
        tempdir = self.makeDir()

        juju_executable = self.makeFile("#!/bin/sh\n" "echo -n $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        expected = (
            "ssh -e %s 0 -C -- sudo cat /tmp/all-machines.log" %
            self.environment_name)

        def callback((out, err)):
            self.assertEqual(expected, out)
            # The content of the file is saved locally.
            with open(os.path.join(tempdir, "all-machines.log")) as logfile:
                logdata = logfile.read()
            self.assertEqual(expected, logdata)

        deferred = self.cli.fetch_file(
            self.environment_name, "/tmp/all-machines.log",
            tempdir)
        deferred.addCallback(callback)
        return deferred

    @inlineCallbacks
    def test_get_all_logs(self):
        """
        Juju1CLI.get_all_logs copies all the Juju model's logs into
        a local file.
        """
        tempdir = self.makeDir()

        juju_executable = self.makeFile("#!/bin/sh\n" "echo -n $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        out, _ = yield self.cli.get_all_logs(
            self.environment_name, tempdir, "all-machines.log")

        expected = ("ssh -e {} 0 -C -- sudo cat /var/log/juju/all-machines.log"
                    ).format(self.environment_name)
        self.assertEqual(expected, out)
        # The content of the file is saved locally.
        with open(os.path.join(tempdir, "all-machines.log")) as logfile:
            logdata = logfile.read()
        self.assertEqual(expected, logdata)


class Juju2CLITest(TwistedTestCase, MockerTestCase):

    def setUp(self):
        super(Juju2CLITest, self).setUp()
        self.juju_data = self.makeDir()
        self.model_name = "maas_env_name"
        self.bootstrap_machine = "maas-name"
        self.bootstrap_cloud = "landscape-maas"
        self.cli = Juju2CLI(self.juju_data)

    @inlineCallbacks
    def test_juju_home_respected(self):
        """Juju2CLI takes a parameter which sets $JUJU_DATA."""
        juju_executable = self.makeFile("#!/bin/sh\necho -n $JUJU_DATA")
        os.chmod(juju_executable, 0755)
        self.assertIs(self.cli.juju_data, self.juju_data)
        self.cli.juju_binary_path = juju_executable

        out, _ = yield self.cli.bootstrap(
            self.model_name, self.bootstrap_machine, self.bootstrap_cloud)
        self.assertEqual(self.juju_data, out)

    @inlineCallbacks
    def test_juju_bootstrap_calls_bootstrap(self):
        """
        Juju2CLI.bootstrap calls juju bootstrap with a model_name
        and the bootstrap_machine as the --to parameter.
        """
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        out, _ = yield self.cli.bootstrap(
            self.model_name, self.bootstrap_machine, self.bootstrap_cloud)

        expected = ("bootstrap -v --no-gui --to {machine} "
                    "--auto-upgrade=false --config {home}/bootstrap.yaml "
                    "landscape-maas {model_name}"
                    ).format(model_name=self.model_name,
                             machine=self.bootstrap_machine,
                             home=self.juju_data)
        self.assertEqual(expected, out)

    @inlineCallbacks
    def test_auto_upgrades_disabled(self):
        """When bootstrapping, auto-upgrades are disabled."""
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        out, _ = yield self.cli.bootstrap(
            self.model_name, self.bootstrap_machine, self.bootstrap_cloud)
        self.assertIn("--auto-upgrade=false", out)

    @inlineCallbacks
    def test_wb_juju_api_info_calls_api_info(self):
        """
        Juju2CLI.api_info calls juju api-info passing the model_name
        parameter.
        """
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable
        self.cli._parse_json_output = lambda (stdout, stderr): stdout

        stdout = yield self.cli.api_info(self.model_name)
        self.assertEqual(
            "show-controller --show-password --format=yaml {}".format(
                self.model_name),
            stdout)

    @inlineCallbacks
    def test_juju_api_info_uses_unicode(self):
        """Juju2CLI.api_info returns API info using unicode strings."""

        details = {
            "ca-cert": "certificate data",
            "uuid": "foo-bar-baz",
            "api-endpoints": ["1.2.3.4:17070", "5.6.7.8:17070"]}
        info = {"controller": {
            "accounts": {
                "admin@local": {"user": "admin@local"}
            },
            "current-account": "admin@local",
            "details": details
        }}
        juju_executable = self.makeFile(
            '#!/bin/sh\necho "%s"' % yaml.dump(info))
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        result = yield self.cli.api_info(self.model_name)
        self.assertTrue(isinstance(result.keys()[0], unicode))
        self.assertTrue(
            isinstance(result["controller"]["details"]["uuid"], unicode))

    @inlineCallbacks
    def test_juju_bootstrap_non_zero(self):
        """Juju2CLI.bootstrap raises CLIError if bootstrap fails.
        """
        juju_executable = self.makeFile("#!/bin/sh\nexit 1")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        deferred = self.cli.bootstrap(
            self.model_name, self.bootstrap_machine, self.bootstrap_cloud)
        self.assertFailure(deferred, CLIError)
        yield deferred
        [failure] = self.flushLoggedErrors(CLIError)
        self.assertEqual(1, failure.value.code)

    @inlineCallbacks
    def test_juju_api_info_non_zero(self):
        """
        Juju2CLI.api_info raises CLIError if the api-info command
        fails.
        """
        juju_executable = self.makeFile("#!/bin/sh\nexit 1")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        deferred = self.cli.api_info(self.model_name)
        self.assertFailure(deferred, CLIError)
        yield deferred
        [failure] = self.flushLoggedErrors(CLIError)
        self.assertEqual(1, failure.value.code)

    @inlineCallbacks
    def test_juju_destroy_environment_calls_destroy_environment(self):
        """
        Juju2CLI.destroy_environment calls juju destroy-environment
        with a model_name and --yes option.
        """
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        out, _ = yield self.cli.destroy_environment(self.model_name)
        self.assertEqual(
            'destroy-controller --yes --destroy-all-models {model}'.format(
                model=self.model_name),
            out)

    @inlineCallbacks
    def test_juju_destroy_environment_forced_calls_kill_controller(self):
        """
        Juju2CLI.destroy_environment with the force flags calls the
        kill-controller operation.
        """
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        out, _ = yield self.cli.destroy_environment(self.model_name, True)
        self.assertEqual("kill-controller --yes", out)

    @inlineCallbacks
    def test_get_juju_status(self):
        """
        The Juju2CLI.get_juju_status method outputs the current juju
        status to a specified file location.
        """
        juju_executable = self.makeFile("#!/bin/sh\n" "echo -n $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        output_file = "/tmp/landscape-logs/juju-status.out"
        expected = "status -m {model} -o {output}".format(
            model=self.model_name,
            output=output_file)

        out, _ = yield self.cli.get_juju_status(
            self.model_name,
            output_file_path=output_file)
        self.assertEqual(expected, out)

    @inlineCallbacks
    def test_fetch_file(self):
        """
        The Juju2CLI.fetch_remote_file copies the specified
        file from a juju machine's filesystem to the local one.
        """
        tempdir = self.makeDir()

        juju_executable = self.makeFile("#!/bin/sh\n" "echo -n $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        expected = "ssh -m {} 0 -C -- sudo cat /tmp/all-machines.log".format(
            self.model_name)

        out, _ = yield self.cli.fetch_file(
            self.model_name, "/tmp/all-machines.log",
            tempdir)
        self.assertEqual(expected, out)
        # The content of the file is saved locally.
        with open(os.path.join(tempdir, "all-machines.log")) as logfile:
            logdata = logfile.read()
        self.assertEqual(expected, logdata)

    @inlineCallbacks
    def test_get_all_logs(self):
        """
        Juju2CLI.get_all_logs copies all the Juju model's logs into
        a local file.
        """
        tempdir = self.makeDir()

        juju_executable = self.makeFile("#!/bin/sh\n" "echo -n $@")
        os.chmod(juju_executable, 0755)
        self.cli.juju_binary_path = juju_executable

        yield self.cli.get_all_logs(
            self.model_name, tempdir, "all-machines.log")

        expected = ("debug-log -m {} --replay --no-tail"
                    ).format(self.model_name)
        # The content of the file is saved locally.
        with open(os.path.join(tempdir, "all-machines.log")) as logfile:
            logdata = logfile.read()
        self.assertEqual(expected, logdata)
