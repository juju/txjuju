# Copyright 2016 Canonical Limited.  All rights reserved.

import os
import os.path
import signal

from twisted.python import log
from twisted.python.failure import Failure
from twisted.test.proto_helpers import MemoryReactorClock
from twisted.trial.unittest import TestCase
from twisted.web.test.test_newclient import StringTransport


SCRIPT = """\
#!/bin/bash

echo $@ > {callfile}
cat << EOF
{output}
EOF
"""


def write_script(dirname, filename="juju", output=None):
    """Write the script to disk at the given location.

    The script will be set with 755 permissions.
    """
    filename = os.path.join(dirname, filename)
    callfile = os.path.join(dirname, ".called")
    script = SCRIPT.format(callfile=callfile, output=output or "")
    with open(filename, "w") as file:
        file.write(script)
    os.chmod(filename, 0o755)
    return filename, callfile


class StubExecutable(object):

    def __init__(self, calls=None):
        if calls is None:
            calls = []
        self.calls = calls

        self.return_resolve_args = None
        self.return_run_out = None

    def resolve_args(self, *args):
        self.calls.append(("resolve_args", args, {}))
        return self.return_resolve_args

    def run(self, *args, **kwargs):
        self.calls.append(("run", args, kwargs))

    def run_out(self, *args, **kwargs):
        self.calls.append(("run_out", args, kwargs))
        return self.return_run_out


class TwistedTestCase(TestCase):

    def setUp(self):
        if log.defaultObserver is not None:
            try:
                log.defaultObserver.stop()
            except ValueError:
                pass

    def tearDown(self):
        if log.defaultObserver is not None:
            log.defaultObserver.start()
        TestCase.tearDown(self)
        # Trial should restore the handler itself, but doesn't.
        # See bug #3888 in Twisted tracker.
        signal.signal(signal.SIGINT, signal.default_int_handler)


class ProtocolMemoryReactor(MemoryReactorClock):
    """A C{MemoryReactor} that will automatically connect a given protocol. """
    def __init__(self, protocol):
        super(ProtocolMemoryReactor, self).__init__()
        self.protocol = protocol
        self.error = None

    def connectSSL(self, host, port, factory, contextFactory, timeout=30,
                   bindAddress=None):
        super(ProtocolMemoryReactor, self).connectSSL(
            host, port, factory, contextFactory)
        if self.error:
            factory.clientConnectionFailed(None, Failure(self.error))
            return
        protocol = factory.buildProtocol(None)
        protocol.makeConnection(StringTransport())
        if self.protocol:
            protocol._wrappedProtocol.deferred.callback(self.protocol)
