# Copyright 2016 Canonical Limited.  All rights reserved.

from cStringIO import StringIO
import json
import os
import os.path

import yaml
from yaml import Loader

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue, Deferred
from twisted.internet.protocol import ProcessProtocol
from twisted.python import log


class JujuCLIError(Exception):
    """Raised when juju fails."""

    def __init__(self, out, err, code=None, signal=None):
        self.out = out
        self.err = err
        self.code = code
        self.signal = signal

        if code is not None:
            reason = "exit code %d" % code
        if signal is not None:
            reason = "signal %d" % signal

        super(JujuCLIError, self).__init__(
            "juju ended with %s (out='%s', err='%s')" % (reason, out, err))


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

        In case of error a L{JujuCLIError} exception will be
        raised with the details of the process run.
        """
        out, err, code = result
        if code != 0:
            error = JujuCLIError(out, err, code=code)
            log.err(error)
            raise error
        return out, err

    def _handle_failure(self, failure):
        """Handle process termination because of a a signal."""
        out, err, signal = failure.value
        error = JujuCLIError(out, err, signal=signal)
        log.err(error)
        raise error


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
             juju_controller_name, cloud_name])

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
        return yaml.load(stdout, UnicodeYamlLoader)

    def _run(self, args=(), outfile=None):
        env = os.environ.copy()
        env["JUJU_DATA"] = self.juju_data
        deferred = spawn_process(
            self.juju_binary_path, args, env=env, outfile=outfile)
        deferred.addCallbacks(self._handle_success, self._handle_failure)
        return deferred

    def _handle_success(self, result):
        """Check that the process terminated with no error.

        In case of error a L{JujuCLIError} exception will be
        raised with the details of the process run.
        """
        out, err, code = result
        if code != 0:
            error = JujuCLIError(out, err, code=code)
            log.err(error)
            raise error
        return out, err

    def _handle_failure(self, failure):
        """Handle process termination because of a a signal."""
        out, err, signal = failure.value
        error = JujuCLIError(out, err, signal=signal)
        log.err(error)
        raise error


class UnicodeYamlLoader(Loader):
    """yaml loader class returning unicode objects instead of python str."""
UnicodeYamlLoader.add_constructor(
    u'tag:yaml.org,2002:str', UnicodeYamlLoader.construct_scalar)


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
