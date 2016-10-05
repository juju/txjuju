# Copyright 2016 Canonical Limited.  All rights reserved.

import signal

from twisted.python import log
from twisted.python.failure import Failure
from twisted.test.proto_helpers import MemoryReactorClock
from twisted.trial.unittest import TestCase
from twisted.web.test.test_newclient import StringTransport


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
