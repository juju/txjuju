# Copyright 2016 Canonical Limited.  All rights reserved.

from collections import namedtuple
import json
import os
import os.path
import shutil
import tempfile
import unittest

import yaml
from mocker import MockerTestCase
from twisted.internet.defer import inlineCallbacks

from txjuju import config, _utils
from txjuju.cli import (
    CLI, Juju1CLI, Juju2CLI, BootstrapSpec, APIInfo, get_executable)
from txjuju.errors import CLIError
from txjuju.testing import TwistedTestCase, StubExecutable, write_script


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


class CLITests(unittest.TestCase):

    def setUp(self):
        super(CLITests, self).setUp()
        self.calls = []
        self.exe = StubExecutable(self.calls)
        self.version_cli = StubJujuXCLI(self.calls)

    def test_from_version_missing_filename(self):
        with self.assertRaises(ValueError):
            CLI.from_version(None, "1.25.6", "/tmp")
        with self.assertRaises(ValueError):
            CLI.from_version("", "1.25.6", "/tmp")

    def test_from_version_missing_version(self):
        with self.assertRaises(ValueError):
            CLI.from_version("juju", None, "/tmp")
        with self.assertRaises(ValueError):
            CLI.from_version("juju", "", "/tmp")

    def test_from_version_unsupported_version(self):
        with self.assertRaises(ValueError):
            CLI.from_version("juju", "1.25.6", None)
        with self.assertRaises(ValueError):
            CLI.from_version("juju", "1.25.6", "")

    def test_missing_executable(self):
        version_cli = object()
        with self.assertRaises(ValueError):
            CLI(None, version_cli)

    def test_missing_version_cli(self):
        class cli(object):
            CFGDIR_ENVVAR = "JUJU_HOME"

        exe = get_executable("juju", cli, "/tmp")
        with self.assertRaises(ValueError):
            CLI(exe, None)

    def test_bootstrap_full(self):
        self.version_cli.return_get_bootstrap_args = ["sub"]
        cli = CLI(self.exe, self.version_cli)
        spec = BootstrapSpec("spam", "lxd")
        cli.bootstrap(spec, "0", "bootstrap.yaml", True, True, True)

        self.assertEqual(self.calls, [
            ("get_bootstrap_args",
             (spec, "0", "bootstrap.yaml", True, True, True), {}),
            ("run", ("sub",), {}),
            ])

    def test_bootstrap_minimal(self):
        self.version_cli.return_get_bootstrap_args = ["sub"]
        cli = CLI(self.exe, self.version_cli)
        spec = BootstrapSpec("spam", "lxd")
        cli.bootstrap(spec)

        self.assertEqual(self.calls, [
            ("get_bootstrap_args",
             (spec, None, None, False, False, False), {}),
            ("run", ("sub",), {}),
            ])

    def test_api_info_full(self):
        self.version_cli.return_get_api_info_args = ["sub"]
        self.exe.return_run_out = "<output>"
        expected = APIInfo(["host"], "admin", "pw")
        self.version_cli.return_parse_api_info = {"spam": expected._asdict()}
        cli = CLI(self.exe, self.version_cli)
        info = cli.api_info("spam")

        self.assertEqual(info, {"spam": expected})
        self.assertEqual(self.calls, [
            ("get_api_info_args", ("spam",), {}),
            ("run_out", ("sub",), {}),
            ("parse_api_info", ("<output>", "spam"), {}),
            ])

    def test_api_info_minimal(self):
        self.version_cli.return_get_api_info_args = ["sub"]
        self.exe.return_run_out = "<output>"
        expected = APIInfo(["host"], "admin", "pw")
        self.version_cli.return_parse_api_info = {"spam": expected._asdict()}
        cli = CLI(self.exe, self.version_cli)
        info = cli.api_info()

        self.assertEqual(info, {"spam": expected})
        self.assertEqual(self.calls, [
            ("get_api_info_args", (None,), {}),
            ("run_out", ("sub",), {}),
            ("parse_api_info", ("<output>", None), {}),
            ])

    def test_destroy_controller_full(self):
        self.version_cli.return_get_destroy_controller_args = ["sub"]
        cli = CLI(self.exe, self.version_cli)
        cli.destroy_controller("spam", True)

        self.assertEqual(self.calls, [
            ("get_destroy_controller_args", ("spam", True), {}),
            ("run", ("sub",), {}),
            ])

    def test_destroy_controller_minimal(self):
        self.version_cli.return_get_destroy_controller_args = ["sub"]
        cli = CLI(self.exe, self.version_cli)
        cli.destroy_controller()

        self.assertEqual(self.calls, [
            ("get_destroy_controller_args", (None, False), {}),
            ("run", ("sub",), {}),
            ])


class StubJujuXCLI(object):

    def __init__(self, calls=None):
        if calls is None:
            calls = []
        self.calls = calls

        self.return_get_bootstrap_args = None
        self.return_get_api_info_args = None
        self.return_parse_api_info = None
        self.return_get_destroy_controller_args = None

    def get_bootstrap_args(self, spec, to=None, cfgfile=None,
                           verbose=False, gui=False, autoupgrade=False):
        self.calls.append(
            ("get_bootstrap_args",
             (spec, to, cfgfile, verbose, gui, autoupgrade), {}))
        return self.return_get_bootstrap_args

    def get_api_info_args(self, controller_name=None):
        self.calls.append(
            ("get_api_info_args", (controller_name,), {}))
        return self.return_get_api_info_args

    def parse_api_info(self, output, controller_name=None):
        self.calls.append(
            ("parse_api_info", (output, controller_name), {}))
        return self.return_parse_api_info

    def get_destroy_controller_args(self, name=None, force=False):
        self.calls.append(
            ("get_destroy_controller_args", (name, force), {}))
        return self.return_get_destroy_controller_args


class CLIJuju1Tests(unittest.TestCase):

    VERSION = "1.25.6"

    API_INFO_JSON = """\
{
    "state-servers": ["[fd1e:9828:924e:a48:216:3eff:fe7f:8125]:17070", "10.235.227.251:17070"],
    "user": "admin",
    "password": "0f154812dd1c02973623c887b2565ea3",
    "environ-uuid": "d3a5befc-c392-4722-85fc-631531e74a09"
}
"""

    def setUp(self):
        super(CLIJuju1Tests, self).setUp()
        self.dirname = tempfile.mkdtemp(prefix="txjuju-test-")
        filename, self.callfile = write_script(self.dirname)
        self.cli = CLI.from_version(filename, self.VERSION, self.dirname)

    def tearDown(self):
        shutil.rmtree(self.dirname)
        super(CLIJuju1Tests, self).tearDown()

    def assert_called(self, args, callfile=None):
        if callfile is None:
            callfile = self.callfile
        with open(callfile) as file:
            called = file.read().strip()
        self.assertEqual(called, args)

    def test_bootstrap_full(self):
        spec = BootstrapSpec("spam", "lxd")
        self.cli.bootstrap(spec, "0", None, True, True, True)

        self.assert_called("bootstrap -v --to 0 -e spam")

    def test_bootstrap_minimal(self):
        spec = BootstrapSpec("spam", "lxd")
        self.cli.bootstrap(spec)

        self.assert_called("bootstrap --no-auto-upgrade -e spam")

    def test_api_info_full(self):
        filename, callfile = write_script(
            self.dirname, output=self.API_INFO_JSON)
        self.cli = CLI.from_version(filename, self.VERSION, self.dirname)
        info = self.cli.api_info("spam")

        self.assert_called(
            "api-info --password --refresh --format=json -e spam", callfile)

    def test_api_info_minimal(self):
        filename, callfile = write_script(
            self.dirname, output=self.API_INFO_JSON)
        self.cli = CLI.from_version(filename, self.VERSION, self.dirname)
        info = self.cli.api_info()

        self.assert_called(
            "api-info --password --refresh --format=json", callfile)

    def test_destroy_controller_full(self):
        self.cli.destroy_controller("spam", True)

        self.assert_called("destroy-environment --yes --force spam")

    def test_destroy_controller_minimal(self):
        self.cli.destroy_controller()

        self.assert_called("destroy-environment --yes")


class CLIJuju2Tests(unittest.TestCase):

    VERSION = "2.0.0"

    API_INFO_YAML = """\
spam:
  details:
    uuid: d3a5befc-c392-4722-85fc-631531e74a09
    api-endpoints: ['[fd1e:9828:924e:a48:216:3eff:fe7f:8125]:17070', '10.235.227.251:17070']
    ca-cert: |
      -----BEGIN CERTIFICATE-----
      MIIDzTCCArWgAwIBAgIUFnfJGYpNsh6YEHcLV6Nz1tvlAfUwDQYJKoZIhvcNAQEL
      BQAwbjENMAsGA1UEChMEanVqdTEuMCwGA1UEAwwlanVqdS1nZW5lcmF0ZWQgQ0Eg
      Zm9yIG1vZGVsICJqdWp1LWNhIjEtMCsGA1UEBRMkMDFhOTYzMTctOWQ2Mi00Yzk5
      LTg4NGYtYzRkZDA2NzI2ZjhhMB4XDTE2MDkxNDIyNTEyM1oXDTI2MDkyMTIyNTEy
      M1owbjENMAsGA1UEChMEanVqdTEuMCwGA1UEAwwlanVqdS1nZW5lcmF0ZWQgQ0Eg
      Zm9yIG1vZGVsICJqdWp1LWNhIjEtMCsGA1UEBRMkMDFhOTYzMTctOWQ2Mi00Yzk5
      LTg4NGYtYzRkZDA2NzI2ZjhhMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKC
      AQEAkacXPhuKhluVFocqUu4xVkjmMweBw32nxu3uX7ZbJeFjMvSXZ8i1dww3RSpc
      LyYWHJr7/58tnx7vK6GGwuUYPSDH4jr3vvhHNwCH7SKQpKa1L6Um2yU/49ovrEsH
      Hv4GtZa8yJtPgnXlyw2IPiMdSFM29jSFGFDu18RxUqbOEqomF6juCAx0PixSx3gO
      u35TvSQ9eeZ+Sr9Pec+zQfd/Q7Ro0xX4eccx0hdYYROqkIr1qhLpC9iWskKpA3+6
      B00fq6h66wFVNwzRd8lC9M3xu3LnTgFzGovLsFc7V15PYknbtjQBKMKfJmr4Clda
      jHijadDjRO+v73ijTHRt4EiyTQIDAQABo2MwYTAOBgNVHQ8BAf8EBAMCAqQwDwYD
      VR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQU1qttJZQOmmIiR/oKYuDuRJz1LaUwHwYD
      VR0jBBgwFoAU1qttJZQOmmIiR/oKYuDuRJz1LaUwDQYJKoZIhvcNAQELBQADggEB
      AIHzvq0dG7ToJRzkuy17GDrGqXgx40NtaIM17pkVlVVFr/HF+t5KiYTwXDVmUk20
      vhodAGe9HDkqHe0jVqa/Jxfv+ixoBOv1zUr4c5LWvhcIiwqR2hN5YjdUZ+0jqOis
      zFAqt3pZt1BIFtGwkiYNhpqbtaiasRAaKbBk+SW3a3DJ357l7jL7O1AZin83UN4H
      ZhH6f3cKg7Rw8De+iwo1+UGZFjFH7VcVevh4W91OkB1vTZJimH/5clxchARO452T
      7KOzQ5vGEZoOZNckSQAErbROJrKXRDscCrIlJrBO8sQczjptkC38wtCbsDbgmkIV
      4Ssxa580yFLWxzcuhlJBpEo=
      -----END CERTIFICATE-----
    cloud: lxd
    region: localhost
  models:
    admin@local/controller:
      uuid: d3a5befc-c392-4722-85fc-631531e74a09
    admin@local/default:
      uuid: b93f17f2-ad56-456d-8051-06e9f7ba46ec
  current-model: admin@local/default
  account:
    user: admin@local
    password: 0f154812dd1c02973623c887b2565ea3
"""

    def setUp(self):
        super(CLIJuju2Tests, self).setUp()
        self.dirname = tempfile.mkdtemp(prefix="txjuju-test-")
        filename, self.callfile = write_script(self.dirname)
        self.cli = CLI.from_version(filename, self.VERSION, self.dirname)

    def tearDown(self):
        shutil.rmtree(self.dirname)
        super(CLIJuju2Tests, self).tearDown()

    def assert_called(self, args, callfile=None):
        if callfile is None:
            callfile = self.callfile
        with open(callfile) as file:
            called = file.read().strip()
        self.assertEqual(called, args)

    def test_bootstrap_full(self):
        spec = BootstrapSpec("spam", "lxd")
        self.cli.bootstrap(spec, "0", "bootstrap.yaml", True, True, True)

        self.assert_called(
            "bootstrap -v --to 0 --config bootstrap.yaml spam lxd")

    def test_bootstrap_minimal(self):
        spec = BootstrapSpec("spam", "lxd")
        self.cli.bootstrap(spec)

        self.assert_called("bootstrap --no-auto-upgrade --no-gui spam lxd")

    def test_api_info_full(self):
        filename, callfile = write_script(
            self.dirname, output=self.API_INFO_YAML)
        self.cli = CLI.from_version(filename, self.VERSION, self.dirname)
        info = self.cli.api_info("spam")

        self.assert_called(
            "show-controller --show-password --format=yaml spam", callfile)

    def test_api_info_minimal(self):
        filename, callfile = write_script(
            self.dirname, output=self.API_INFO_YAML)
        self.cli = CLI.from_version(filename, self.VERSION, self.dirname)
        info = self.cli.api_info()

        self.assert_called(
            "show-controller --show-password --format=yaml", callfile)

    def test_destroy_controller_full(self):
        self.cli.destroy_controller("spam", True)

        self.assert_called("kill-controller --yes spam")

    def test_destroy_controller_minimal(self):
        self.cli.destroy_controller()

        self.assert_called("destroy-controller --yes --destroy-all-models")


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
