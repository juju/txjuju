# Copyright 2016 Canonical Limited.  All rights reserved.

import json
import logging
import os
import os.path
from collections import namedtuple
from cStringIO import StringIO

import yaml
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue, Deferred
from twisted.internet.protocol import ProcessProtocol
from twisted.python import log

from . import config, _utils, _juju1, _juju2
from .errors import CLIError


def get_executable(filename, version_cli, cfgdir, envvars=None):
    """Return the Executable for the given juju binary.

    @param filename: The path to the juju binary.
    @param version_cli: The version-specific JujuXCLI to use.
    @param cfgdir: The Juju config dir to use.
    @param envvars: The additional environment variables to use.
    """
    if not version_cli:
        raise ValueError("missing version_cli")
    if not cfgdir:
        raise ValueError("missing cfgdir")

    if envvars is None:
        envvars = os.environ
    envvars = dict(envvars)
    envvars[version_cli.CFGDIR_ENVVAR] = cfgdir

    return _utils.Executable(filename, envvars)


class BootstrapSpec(object):
    """A specification of the information with which to bootstrap."""

    DEFAULT_SERIES = "trusty"

    def __init__(self, name, driver, default_series=None, admin_secret=None):
        """
        @param name: The name of the controller to bootstrap.
        @param driver: The provider type to use.
        @param default_series: The OS series to provision by default.
            If not provided, it defaults to trusty.
        @param admin_secret: The password to use for the admin user,
            if any.
        """
        if default_series is None:
            default_series = self.DEFAULT_SERIES

        self.name = name
        self.driver = driver
        self.default_series = default_series
        self.admin_secret = admin_secret

    _fields = __init__.__code__.co_varnames[1:]

    def __repr__(self):
        return "{}({})".format(
            type(self).__name__,
            ', '.join("{}={!r}".format(name, getattr(self, name))
                      for name in self._fields),
            )

    def __eq__(self, other):
        for name in self._fields:
            try:
                other_val = getattr(other, name)
            except AttributeError:
                # TODO Return NotImplemented?
                return False
            if getattr(self, name) != other_val:
                return False
        return True

    def __ne__(self, other):
        return not (self == other)

    def config(self):
        """Return the JujuConfig corresponding to this spec."""
        controller = config.ControllerConfig.from_info(
            self.name,
            self.driver,
            cloud_name=self.driver,
            default_series=self.default_series,
            admin_secret=self.admin_secret,
            )
        return config.Config(controller)


class APIInfo(namedtuple("APIInfo", "endpoints user password model_uuid")):
    """The API information provided by the Juju CLI."""

    def __new__(cls, endpoints, user, password, model_uuid=None):
        """
        @param endpoints: The Juju server's API root endpoints.
        @param user: The Juju user with which to connect.
        @param password: The user's password.
        @param model_uuid: The UUID of the model to manage via the API.
            If this is None then only controller-level API facades
            should be used.
        """
        if endpoints:
            endpoints = tuple(unicode(ep) for ep in endpoints)
        else:
            endpoints = None
        user = unicode(user) if user else None
        password = unicode(password) if password else None
        model_uuid = unicode(model_uuid) if model_uuid else None
        return super(APIInfo, cls).__new__(
            cls, endpoints, user, password, model_uuid)

    def __init__(self, *args, **kwargs):
        if not self.endpoints:
            raise ValueError("missing endpoints")
        if not self.user:
            raise ValueError("missing user")
        if not self.password:
            raise ValueError("missing password")

    @property
    def address(self):
        """The primary API endpoint address to use."""
        return self.endpoints[0]


class CLI(object):
    """The client CLI for some Juju version."""

    @classmethod
    def from_version(cls, filename, version, cfgdir, envvars=None):
        """Return a new CLI for the given binary and version.

        @param filename: The path to the juju binary.
        @param version: The Juju version to use.
        @param cfgdir: The path to the "juju home" directory.
        @param envvars: The extra environment variables to use when
            running the juju command.  If not set then os.environs
            is used.
        """
        if not version:
            raise ValueError("missing version")
        elif version.startswith("1."):
            juju = _juju1.CLIHooks()
        elif version.startswith("2."):
            juju = _juju2.CLIHooks()
        else:
            raise ValueError("unsupported Juju version {!r}".format(version))

        executable = get_executable(filename, juju, cfgdir, envvars)
        return cls(executable, juju)

    def __init__(self, executable, version_cli):
        """
        @param executable: The Executable to use.
        @param version_cli: The version-specific subcommand handler.
        """
        if not executable:
            raise ValueError("missing executable")
        if version_cli is None:
            raise ValueError("missing version_cli")
        self._exe = executable
        self._juju = version_cli

    @property
    def executable(self):
        """The Executable used by this CLI."""
        return self._exe

    def bootstrap(self, spec, to=None, cfgfile=None,
                  verbose=False, gui=False, autoupgrade=False):
        """Bootstrap a new Juju controller.

        @param spec: The BootstrapSpec to use.
        @param to: The machine ID to which to deploy the API server.
        @param cfgfile: The bootstrap config file to use.
        @param verbose: Produce more verbose output.
        @param gui: Install and start the JUJU GUI for the controller.
        @param autoupgrade: Perform automatic upgrades of Ubuntu.
        """
        args = self._juju.get_bootstrap_args(
            spec, to, cfgfile, verbose, gui, autoupgrade)
        self._exe.run(*args)

    def api_info(self, controller_name=None):
        """Return {<model name>: APIInfo} for each of the controller's models.

        One entry is included for the controller-level API facades.  The
        key for that entry is None.
        """
        args = self._juju.get_api_info_args(controller_name)
        out = self._exe.run_out(*args)
        infos = self._juju.parse_api_info(out, controller_name)
        return {modelname: APIInfo(**info)
                for modelname, info in infos.items()}

    def destroy_controller(self, name=None, force=False):
        """Destroy the controller."""
        args = self._juju.get_destroy_controller_args(name, force)
        self._exe.run(*args)


# TODO Use _juju1,CLIHooks in the twisted code here.

class Juju1CLI(object):

    # Allow override for testing purposes, normal use should not need
    # to change this.
    juju_binary_path = "juju"

    def __init__(self, juju_home):
        self.juju_home = juju_home

    def bootstrap(self, environment_name, bootstrap_machine):
        """Run juju bootstrap against the specified C{environment_name}.

        The passed in machine name will be used as the bootstrap node,
        which should be a MAAS machine name.

        Automatic upgrades are disabled during the bootstrap.
        """
        return self._run(
            ["bootstrap", "-v", "-e", environment_name, "--to",
             bootstrap_machine, "--no-auto-upgrade"])

    def api_info(self, environment_name):
        """Run juju api-info against the specified environment.

        @return: a deferred returning API information.
        """
        deferred = self._run(
            ["api-info", "-e", environment_name, "--refresh",
             "--format=json"])
        deferred.addCallback(self._parse_json_output)
        return deferred

    def destroy_environment(self, environment_name, force=False):
        """Run juju destroy-environment against C{environment_name}."""
        cmd = ["destroy-environment", "--yes"]
        if force:
            cmd.append("--force")
        cmd.append(environment_name)
        return self._run(cmd)

    @inlineCallbacks
    def fetch_file(self, environment_name, remote_path, local_dir,
                   machine="0"):
        """Copy a file from a remote juju machine to the local filesystem.

        It uses sudo as root on the remote host, to avoid read permission
        errors.

        @param environment_name: The name of the environment to operate in.
        @param remote_path: The full path of the file on the remote machine.
        @param local_dir: The local directory the remote file will be copied
            to.
        @param machine: Optionally, which machine to fetch the file from.
            Defaults to the bootstrap node (machine 0).
        """
        copy_command = [
            "ssh", "-e", environment_name, machine, "-C",  # Compress
            "--", "sudo cat %s" % remote_path]

        out, err = yield self._run(copy_command)
        local_path = os.path.join(local_dir, os.path.basename(remote_path))
        with open(local_path, "w") as file:
            file.write(out)
        returnValue((out, err))

    def get_juju_status(self, environment_name, output_file_path):
        """
        Prints the output of the "juju status" command to the specified file.

        @param environment_name: The name of the environment to operate in.
        @param output_file_path: The full path to a local file to which the
            output of the juju status command will be written.
        """
        status_command = ["status", "-e", environment_name, "-o",
                          output_file_path]

        return self._run(status_command)

    def get_all_logs(self, envname, destdir, filename):
        """Copy all of the environment's logs into the given file."""
        return self.fetch_file(
            envname,
            remote_path=os.path.join("/var/log/juju/", filename),
            local_dir=destdir)

    def _parse_json_output(self, (stdout, stderr)):
        """Parse JSON output from the juju process."""
        return json.loads(stdout)

    def _run(self, args=()):
        env = os.environ.copy()
        env["JUJU_HOME"] = self.juju_home
        deferred = spawn_process(self.juju_binary_path, args, env=env)
        deferred.addCallbacks(self._handle_success, self._handle_failure)
        return deferred

    def _handle_success(self, result):
        """Check that the process terminated with no error.

        In case of error a CLIError exception will be
        raised with the details of the process run.
        """
        out, err, code = result
        if code != 0:
            error = CLIError(out, err, code=code)
            log.err(error)
            raise error
        return out, err

    def _handle_failure(self, failure):
        """Handle process termination because of a a signal."""
        out, err, signal = failure.value
        error = CLIError(out, err, signal=signal)
        log.err(error)
        raise error


# TODO Use _juju2,CLIHooks in the twisted code here.

class Juju2CLI(object):

    # Allow override for testing purposes, normal use should not need
    # to change this.
    juju_binary_path = "juju-2.0"

    def __init__(self, juju_data):
        """The JUJU_DATA path, previously referred as JUJU_HOME."""
        self.juju_data = juju_data

    def bootstrap(self, juju_controller_name, bootstrap_machine, cloud_name):
        """Run juju bootstrap against the specified juju_model_name.

        The passed in machine name will be used as the bootstrap node,
        which should be a MAAS machine name.

        Automatic upgrades are disabled during the bootstrap.
        """
        bootstrap_config = os.path.join(self.juju_data, 'bootstrap.yaml')
        # XXX Drop --no-gui when fixing juju-gui feature flag #1555292
        return self._run(
            ["bootstrap", "-v", "--no-gui", "--to", bootstrap_machine,
             "--auto-upgrade=false", "--config", bootstrap_config,
             cloud_name, juju_controller_name])

    def api_info(self, juju_controller_name):
        """Run get api info for the specified model/controller.

        @return: a deferred returning API information.
        """
        # RELEASE_BLOCKER once lp:1576366 is resolved, return to --format=json
        deferred = self._run(
            ["show-controller", "--show-password", "--format=yaml",
             juju_controller_name])
        deferred.addCallback(self._parse_yaml_output)
        return deferred

    def destroy_environment(self, juju_controller_name, force=False):
        """Run juju destroy-controller against juju_model_name.

        The force parameter disappeared with juju2 and was replaced by
        kill-controller command.
        """
        if force:
            # RELEASE_BLOCKER kill-controller may go away juju-2.0 goes out
            # of beta so we should use whatever gets in the juju2 release.
            cmd = ["kill-controller", "--yes"]
        else:
            cmd = ["destroy-controller", "--yes", "--destroy-all-models",
                   juju_controller_name]
        return self._run(cmd)

    @inlineCallbacks
    def fetch_file(self, juju_model_name, remote_path, local_dir, machine="0"):
        """Copy a file from a remote juju machine to the local filesystem.

        It uses sudo as root on the remote host, to avoid read permission
        errors.

        @param juju_model_name: The name of the model to operate in.
        @param remote_path: The full path of the file on the remote machine.
        @param local_dir: The local directory the remote file will be copied
            to.
        @param machine: Optionally, which machine to fetch the file from.
            Defaults to the bootstrap node (machine 0).
        """
        copy_command = [
            "ssh", "-m", juju_model_name, machine, "-C",  # Compress
            "--", "sudo cat %s" % remote_path]

        out, err = yield self._run(copy_command)
        local_path = os.path.join(local_dir, os.path.basename(remote_path))
        with open(local_path, "w") as file:
            file.write(out)
        returnValue((out, err))

    def get_juju_status(self, juju_model_name, output_file_path):
        """
        Prints the output of the "juju status" command to the specified file.

        @param juju_model_name: The name of the model to operate in.
        @param output_file_path: The full path to a local file to which the
            output of the juju status command will be written.
        """
        status_command = ["status", "-m", juju_model_name, "-o",
                          output_file_path]

        return self._run(status_command)

    @inlineCallbacks
    def get_all_logs(self, modelname, destdir, filename):
        """Copy all of the model's logs into the given file."""
        cmd = ["debug-log",
               "-m", modelname,
               "--replay",
               "--no-tail",
               ]
        env = os.environ.copy()
        env["JUJU_DATA"] = self.juju_data
        with open(os.path.join(destdir, filename), "w") as logfile:
            yield self._run(cmd, logfile)

    def _parse_json_output(self, (stdout, stderr)):
        """Parse JSON output from the juju process."""
        return json.loads(stdout)

    def _parse_yaml_output(self, (stdout, stderr)):
        """Parse YAML output from the juju process."""
        return yaml.load(stdout, _utils.UnicodeYamlLoader)

    def _run(self, args=(), outfile=None):
        env = os.environ.copy()
        env["JUJU_DATA"] = self.juju_data
        deferred = spawn_process(
            self.juju_binary_path, args, env=env, outfile=outfile)
        deferred.addCallbacks(self._handle_success, self._handle_failure)
        return deferred

    def _handle_success(self, result):
        """Check that the process terminated with no error.

        In case of error a CLIError exception will be
        raised with the details of the process run.
        """
        out, err, code = result
        if code != 0:
            error = CLIError(out, err, code=code)
            log.err(error)
            raise error
        return out, err

    def _handle_failure(self, failure):
        """Handle process termination because of a a signal."""
        out, err, signal = failure.value
        error = CLIError(out, err, signal=signal)
        log.err(error)
        raise error


def spawn_process(executable, args, env, outfile=None):
    """Spawn a process using Twisted reactor.

    Return a deferred which will be called with process stdout, stderr
    and exit code.  If outfile is provided then the stdout and stderr
    stings will be empty.

    Note: this is a variant of landscape.lib.twisted_util.spawn_process
    that supports streaming to a file.
    """
    list_args = [executable]
    list_args.extend(args)

    logging.info("running {!r}".format(" ".join(list_args)))
    import pprint
    logging.info("OS env:\n" + pprint.pformat(env))

    result = Deferred()
    if outfile is None:
        protocol = AllOutputProcessProtocol(result)
    else:
        protocol = StreamToFileProcessProtocol(result, outfile)
    reactor.spawnProcess(protocol, executable, args=list_args, env=env)
    return result


class AllOutputProcessProtocol(ProcessProtocol):
    """A process protocol for getting stdout, stderr and exit code.

    (based on landscape.lib.twisted_util.AllOutputProcessProtocol)
    """

    def __init__(self, deferred):
        self.deferred = deferred
        self.outBuf = StringIO()
        self.errBuf = StringIO()
        self.errReceived = self.errBuf.write

    def outReceived(self, data):
        self.outBuf.write(data)

    def processEnded(self, reason):
        out = self.outBuf.getvalue()
        err = self.errBuf.getvalue()
        e = reason.value
        code = e.exitCode
        if e.signal:
            self.deferred.errback((out, err, e.signal))
        else:
            self.deferred.callback((out, err, code))


class StreamToFileProcessProtocol(ProcessProtocol):
    """A process protocol that writes the output to a file."""

    def __init__(self, deferred, outfile, errfile=None):
        geterr = None
        if errfile is None:
            errfile = StringIO()
            geterr = errfile.getvalue
        self.deferred = deferred
        self.outfile = outfile
        self.errfile = errfile
        self.geterr = geterr

    def outReceived(self, data):
        self.outfile.write(data)

    def errReceived(self, data):
        self.errfile.write(data)

    def processEnded(self, reason):
        out = ""
        err = self.geterr() if self.geterr else ""
        e = reason.value
        if e.signal:
            self.deferred.errback((out, err, e.signal))
        else:
            self.deferred.callback((out, err, e.exitCode))
