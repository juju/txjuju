# Copyright 2016 Canonical Limited.  All rights reserved.

import os
import json

import yaml
from mocker import MockerTestCase
from twisted.internet.defer import inlineCallbacks

from txjuju.testing import TwistedTestCase
from txjuju.process import Juju1Process, Juju2Process, JujuProcessError


class Juju1ProcessTest(TwistedTestCase, MockerTestCase):
    # XXX bug #1558600 to be removed with juju2 feature flag

    def setUp(self):
        super(Juju1ProcessTest, self).setUp()
        self.juju_home = self.makeDir()
        self.environment_name = "maas_env_name"
        self.bootstrap_machine = "maas-name"
        self.process = Juju1Process(self.juju_home)

    def test_juju_home_respected(self):
        """L{JujuProcess} takes a parameter which sets $JUJU_HOME."""
        juju_executable = self.makeFile("#!/bin/sh\necho -n $JUJU_HOME")
        os.chmod(juju_executable, 0755)
        self.assertIs(self.process.juju_home, self.juju_home)
        self.process.juju_binary_path = juju_executable

        def callback(result):
            out, err = result
            self.assertEqual(self.juju_home, out)
        deferred = self.process.bootstrap(
            self.environment_name, self.bootstrap_machine)
        deferred.addCallback(callback)
        return deferred

    def test_juju_bootstrap_calls_bootstrap(self):
        """
        JujuProcess.bootstrap calls juju bootstrap with an C{environment_name}
        and the C{bootstrap_machine} as the --to parameter.
        """
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        def callback(result):
            out, err = result
            self.assertEqual(
                "bootstrap -v -e %s --to %s --no-auto-upgrade" % (
                    self.environment_name, self.bootstrap_machine),
                out)
        deferred = self.process.bootstrap(
            self.environment_name, self.bootstrap_machine)
        deferred.addCallback(callback)
        return deferred

    def test_auto_upgrades_disabled(self):
        """When bootstrapping, auto-upgrades are disabled."""
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        def callback(result):
            out, err = result
            self.assertIn("--no-auto-upgrade", out)

        deferred = self.process.bootstrap(
            self.environment_name, self.bootstrap_machine)
        deferred.addCallback(callback)
        return deferred

    def test_wb_juju_api_info_calls_api_info(self):
        """
        JujuProcess.api_info calls juju api-info passing the environment_name
        parameter.
        """
        juju_executable = self.makeFile("#!/bin/sh\necho $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable
        self.process._parse_json_output = lambda (stdout, stderr): stdout

        def callback(stdout):
            self.assertEqual(
                "api-info -e %s --refresh --format=json\n" %
                self.environment_name,
                stdout)
        deferred = self.process.api_info(self.environment_name)
        deferred.addCallback(callback)
        return deferred

    def test_juju_api_info(self):
        """JujuProcess.api_info returns API info."""

        info = {
            "ca-cert": "certificate data",
            "environ-uuid": "foo-bar-baz",
            "state-servers": ["1.2.3.4:17070", "5.6.7.8:17070"],
            "user": "admin"}
        juju_executable = self.makeFile(
            "#!/bin/sh\necho '%s'" % json.dumps(info))
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        def callback(result):
            self.assertEqual(info, result)

        deferred = self.process.api_info(self.environment_name)
        deferred.addCallback(callback)
        return deferred

    def test_juju_bootstrap_non_zero(self):
        """JujuProcess.bootstrap raises JujuProcessError if bootstrap fails."""
        juju_executable = self.makeFile("#!/bin/sh\nexit 1")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        def callback(_):
            [failure] = self.flushLoggedErrors(JujuProcessError)
            self.assertEqual(1, failure.value.code)

        deferred = self.process.bootstrap(
            self.environment_name, self.bootstrap_machine)
        self.assertFailure(deferred, JujuProcessError)
        deferred.addCallback(callback)
        return deferred

    def test_juju_destroy_environment_calls_destroy_environment(self):
        """
        C{JujuProcess.destroy_environment} calls juju destroy-environment
        with an C{environment_name} and --yes option.
        """
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        def callback((out, err)):
            self.assertEqual(
                'destroy-environment --yes %s' % self.environment_name,
                out)

        deferred = self.process.destroy_environment(self.environment_name)
        deferred.addCallback(callback)
        return deferred

    def test_juju_destroy_environment_calls_destroy_environment_force(self):
        """
        C{JujuProcess.destroy_environment} calls juju destroy-environment
        with the --force parameter if C{force} is C{True}.
        """
        juju_executable = self.makeFile("#!/bin/sh\n" "echo -n $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        def callback((out, err)):
            self.assertEqual(
                'destroy-environment --yes --force %s' % self.environment_name,
                out)

        deferred = self.process.destroy_environment(
            self.environment_name, force=True)
        deferred.addCallback(callback)
        return deferred

    def test_get_juju_status(self):
        """
        The C{JujuProcess.get_juju_status} method outputs the current juju
        status to a specified file location.
        """
        juju_executable = self.makeFile("#!/bin/sh\n" "echo -n $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        expected = ("status -e %s -o /tmp/landscape-logs/juju-status.out")

        def callback((out, err)):
            self.assertEqual(
                expected % self.environment_name, out)

        deferred = self.process.get_juju_status(
            self.environment_name,
            output_file_path="/tmp/landscape-logs/juju-status.out")
        deferred.addCallback(callback)
        return deferred

    def test_fetch_file(self):
        """
        The C{JujuProcess.fetch_remote_file} copies the specified
        file from a juju machine's filesystem to the local one.
        """
        tempdir = self.makeDir()

        juju_executable = self.makeFile("#!/bin/sh\n" "echo -n $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        expected = (
            "ssh -e %s 0 -C -- sudo cat /tmp/all-machines.log" %
            self.environment_name)

        def callback((out, err)):
            self.assertEqual(expected, out)
            # The content of the file is saved locally.
            with open(os.path.join(tempdir, "all-machines.log")) as logfile:
                logdata = logfile.read()
            self.assertEqual(expected, logdata)

        deferred = self.process.fetch_file(
            self.environment_name, "/tmp/all-machines.log",
            tempdir)
        deferred.addCallback(callback)
        return deferred

    @inlineCallbacks
    def test_get_all_logs(self):
        """
        Juju1Process.get_all_logs copies all the Juju model's logs into
        a local file.
        """
        tempdir = self.makeDir()

        juju_executable = self.makeFile("#!/bin/sh\n" "echo -n $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        out, _ = yield self.process.get_all_logs(
            self.environment_name, tempdir, "all-machines.log")

        expected = ("ssh -e {} 0 -C -- sudo cat /var/log/juju/all-machines.log"
                    ).format(self.environment_name)
        self.assertEqual(expected, out)
        # The content of the file is saved locally.
        with open(os.path.join(tempdir, "all-machines.log")) as logfile:
            logdata = logfile.read()
        self.assertEqual(expected, logdata)


class Juju2ProcessTest(TwistedTestCase, MockerTestCase):

    def setUp(self):
        super(Juju2ProcessTest, self).setUp()
        self.juju_data = self.makeDir()
        self.model_name = "maas_env_name"
        self.bootstrap_machine = "maas-name"
        self.bootstrap_cloud = "landscape-maas"
        self.process = Juju2Process(self.juju_data)

    @inlineCallbacks
    def test_juju_home_respected(self):
        """Juju2Process takes a parameter which sets $JUJU_DATA."""
        juju_executable = self.makeFile("#!/bin/sh\necho -n $JUJU_DATA")
        os.chmod(juju_executable, 0755)
        self.assertIs(self.process.juju_data, self.juju_data)
        self.process.juju_binary_path = juju_executable

        out, _ = yield self.process.bootstrap(
            self.model_name, self.bootstrap_machine, self.bootstrap_cloud)
        self.assertEqual(self.juju_data, out)

    @inlineCallbacks
    def test_juju_bootstrap_calls_bootstrap(self):
        """
        Juju2Process.bootstrap calls juju bootstrap with a model_name
        and the bootstrap_machine as the --to parameter.
        """
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        out, _ = yield self.process.bootstrap(
            self.model_name, self.bootstrap_machine, self.bootstrap_cloud)
        self.assertEqual(
            "bootstrap -v --no-gui --to {machine} --auto-upgrade=false "
            "--config {home}/bootstrap.yaml {model_name} "
            "landscape-maas".format(
                model_name=self.model_name,
                machine=self.bootstrap_machine,
                home=self.juju_data),
            out)

    @inlineCallbacks
    def test_auto_upgrades_disabled(self):
        """When bootstrapping, auto-upgrades are disabled."""
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        out, _ = yield self.process.bootstrap(
            self.model_name, self.bootstrap_machine, self.bootstrap_cloud)
        self.assertIn("--auto-upgrade=false", out)

    @inlineCallbacks
    def test_wb_juju_api_info_calls_api_info(self):
        """
        Juju2Process.api_info calls juju api-info passing the model_name
        parameter.
        """
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable
        self.process._parse_json_output = lambda (stdout, stderr): stdout

        stdout = yield self.process.api_info(self.model_name)
        self.assertEqual(
            "show-controller --show-password --format=yaml {}".format(
                self.model_name),
            stdout)

    @inlineCallbacks
    def test_juju_api_info_uses_unicode(self):
        """Juju2Process.api_info returns API info using unicode strings."""

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
        self.process.juju_binary_path = juju_executable

        result = yield self.process.api_info(self.model_name)
        self.assertTrue(isinstance(result.keys()[0], unicode))
        self.assertTrue(
            isinstance(result["controller"]["details"]["uuid"], unicode))

    @inlineCallbacks
    def test_juju_bootstrap_non_zero(self):
        """Juju2Process.bootstrap raises JujuProcessError if bootstrap fails.
        """
        juju_executable = self.makeFile("#!/bin/sh\nexit 1")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        deferred = self.process.bootstrap(
            self.model_name, self.bootstrap_machine, self.bootstrap_cloud)
        self.assertFailure(deferred, JujuProcessError)
        yield deferred
        [failure] = self.flushLoggedErrors(JujuProcessError)
        self.assertEqual(1, failure.value.code)

    @inlineCallbacks
    def test_juju_api_info_non_zero(self):
        """
        Juju2Process.api_info raises JujuProcessError if the api-info command
        fails.
        """
        juju_executable = self.makeFile("#!/bin/sh\nexit 1")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        deferred = self.process.api_info(self.model_name)
        self.assertFailure(deferred, JujuProcessError)
        yield deferred
        [failure] = self.flushLoggedErrors(JujuProcessError)
        self.assertEqual(1, failure.value.code)

    @inlineCallbacks
    def test_juju_destroy_environment_calls_destroy_environment(self):
        """
        Juju2Process.destroy_environment calls juju destroy-environment
        with a model_name and --yes option.
        """
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        out, _ = yield self.process.destroy_environment(self.model_name)
        self.assertEqual(
            'destroy-controller --yes --destroy-all-models {model}'.format(
                model=self.model_name),
            out)

    @inlineCallbacks
    def test_juju_destroy_environment_forced_calls_kill_controller(self):
        """
        Juju2Process.destroy_environment with the force flags calls the
        kill-controller operation.
        """
        juju_executable = self.makeFile("#!/bin/sh\necho -n $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        out, _ = yield self.process.destroy_environment(self.model_name, True)
        self.assertEqual("kill-controller --yes", out)

    @inlineCallbacks
    def test_get_juju_status(self):
        """
        The Juju2Process.get_juju_status method outputs the current juju
        status to a specified file location.
        """
        juju_executable = self.makeFile("#!/bin/sh\n" "echo -n $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        output_file = "/tmp/landscape-logs/juju-status.out"
        expected = "status -m {model} -o {output}".format(
            model=self.model_name,
            output=output_file)

        out, _ = yield self.process.get_juju_status(
            self.model_name,
            output_file_path=output_file)
        self.assertEqual(expected, out)

    @inlineCallbacks
    def test_fetch_file(self):
        """
        The Juju2Process.fetch_remote_file copies the specified
        file from a juju machine's filesystem to the local one.
        """
        tempdir = self.makeDir()

        juju_executable = self.makeFile("#!/bin/sh\n" "echo -n $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        expected = "ssh -m {} 0 -C -- sudo cat /tmp/all-machines.log".format(
            self.model_name)

        out, _ = yield self.process.fetch_file(
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
        Juju2Process.get_all_logs copies all the Juju model's logs into
        a local file.
        """
        tempdir = self.makeDir()

        juju_executable = self.makeFile("#!/bin/sh\n" "echo -n $@")
        os.chmod(juju_executable, 0755)
        self.process.juju_binary_path = juju_executable

        yield self.process.get_all_logs(
            self.model_name, tempdir, "all-machines.log")

        expected = ("debug-log -m {} --replay --no-tail"
                    ).format(self.model_name)
        # The content of the file is saved locally.
        with open(os.path.join(tempdir, "all-machines.log")) as logfile:
            logdata = logfile.read()
        self.assertEqual(expected, logdata)
