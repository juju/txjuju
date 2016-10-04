# Copyright 2016 Canonical Limited.  All rights reserved.

import os
import json
import signal
import subprocess

from testtools.content import content_from_file

from fixtures import Fixture, TempDir, EnvironmentVariable

from twisted.python import log
from twisted.python.failure import Failure
from twisted.internet.error import ConnectionDone, ConnectionLost
from twisted.internet.defer import Deferred, succeed
from twisted.test.proto_helpers import MemoryReactorClock
from twisted.trial.unittest import TestCase
from twisted.web.test.test_newclient import StringTransport

from .errors import CLIError
from .protocol import APIClientProtocol


FAKE_JUJU_VERSION = "1.25.6"
FAKE_JUJU_BINARY = "/usr/bin/fake-juju-%s" % FAKE_JUJU_VERSION
FAKE_JUJU_ENVIRONMENTS_YAML = """environments:
    test:
        admin-secret: test
        default-series: trusty
        type: dummy
"""


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


class FakeAPIBackend(object):
    """A fake transport for an APIClientProtocol.

    @ivar requests: Map request IDs to their payload.
    """

    def __init__(self, version=1):
        self.requests = {}
        self.pending = []
        self.protocol = APIClientProtocol()
        self.protocol.makeConnection(self)
        self.connected = True
        self.version = version

    # ITransport APIs

    def write(self, data):
        payload = json.loads(data)
        request_id = payload["RequestId"]
        self.pending.append(request_id)
        self.requests[request_id] = payload

    def loseConnection(self):
        self.connected = False
        reason = Failure(ConnectionLost("Lost the connection"))
        self.protocol.connectionLost(reason)

    # Test-oriented APIs

    @property
    def last(self):
        return self.requests[max(self.requests.keys())]

    @property
    def lastType(self):
        return self.last["Type"]

    @property
    def lastVersion(self):
        return self.last.get("Version")

    @property
    def lastRequest(self):
        return self.last["Request"]

    @property
    def lastId(self):
        return self.last["Id"]

    @property
    def lastParams(self):
        return self.last["Params"]

    @property
    def lastRequestId(self):
        return self.last["RequestId"]

    def response(self, response, requestId=None):
        """Fire response data for the request with the given ID.

        If no ID is given, the default is to use the last one.
        """
        payload = {"Response": response}
        self._fire(payload, requestId)

    def responseLogin(self, endpoints=[u"host"]):
        api_servers = [
            [{"NetworkName": "net-%d" % index,
              "Port": 17070,
              "Scope": "local-cloud",
              "Type": "ipv4",
              "Value": endpoint}]
            for index, endpoint in enumerate(endpoints)]
        return self.response(
            {"EnvironTag": "environment-uuid-123",
             "Servers": api_servers})

    def responseWatchAll(self):
        self.response({u"AllWatcherId": "1"})

    def responseLoginAndWatchAll(self):
        self.responseLogin()
        self.responseWatchAll()

    def responseDeltas(self, deltas):
        """Fire a response for the AllWatcher Next API.

        @param deltas: The list of deltas to fire. Each delta is either an
            instance of a Juju entity (from c.juju.entity) or a 2-tuple of
            the form (<instance>, <verb>), where <instance> is the Juju
            entity and <verb> is either 'change' or 'remove'.
        """
        responses = []
        for delta in deltas:
            if not isinstance(delta, tuple):
                delta = (delta, "change")
            formatter = getattr(self, "_format" + delta[0].__class__.__name__)
            responses.append(formatter(*delta))

        self.response({u"Deltas": responses})

    def responseSetAnnotations(self, requestId=None):
        self.response({})

    def responseServiceGet(self, name, config={}):
        self.response(
            {"Service": name,
             "Charm": name,
             "Constraints": {},
             "Config": config})

    def error(self, exception, requestId=None):
        """Fire an error for the request with the given ID.

        If no ID is given, the default is to use the last one.
        """
        payload = {"Error": exception.error, "ErrorCode": exception.code}
        self._fire(payload, requestId)

    def _fire(self, payload, requestId):
        if requestId is None:
            # If no requestId is specified, we take the oldest pending request
            requestId = self.pending[0]
        payload["RequestId"] = requestId
        self.pending.remove(requestId)
        self.protocol.dataReceived(json.dumps(payload))

    def _formatAnnotationInfo(self, info, verb):
        return ["annotation", verb, {
            "Annotations": info.pairs,
            "Tag": info.name}]

    def _formatJujuApplicationInfo(self, info, verb):
        if self.version == 1:
            entityName = "service"
        else:
            entityName = "application"
        return [entityName, verb, {
            "Name": info.name,
            "CharmURL": info.charmURL}]

    def _formatUnitInfo(self, info, verb):
        return ["unit", verb, {
            "Name": info.name,
            "Service": info.applicationName,
            "CharmURL": info.charmURL}]

    def _formatMachineInfo(self, info, verb):
        return ["machine", verb, {
            "Id": info.id,
            "InstanceId": info.instanceId,
            "Status": info.status}]


class FakeAPIClientProtocol(object):
    """A fake APIClientProtocol.

    @ivar requests: A list of tuples of the form (entityType, request,
        entityId, params) holding the arguments passed to C{sendRequest} calls.
    @ivar request: Arguments to the last issued request.
    """
    connected = True

    def __init__(self):
        self.disconnected = Deferred()
        self._pending_requests = []
        self._queued_errors = []
        self._queued_responses = []

    def sendRequest(self, entityType, requestInfo, entityId=None, params=None,
                    facade_version=1):
        request = (entityType, requestInfo, entityId, params, facade_version)
        response = Deferred()
        if self._queued_errors:
            reason = self._queued_errors.pop(0)
            response.errback(reason)
        elif self._queued_responses:
            prepType, prepInfo, content = self._queued_responses.pop(0)
            assert prepType == entityType
            assert prepInfo == requestInfo
            response.callback(content)
        else:
            self._pending_requests.append((request, response))
        return response

    @property
    def request(self):
        """Return the last pending request."""
        if self._pending_requests:
            return self._pending_requests[-1][0]

    @property
    def requests(self):
        return [request for request, _ in self._pending_requests]

    def response(self, entityType, request, content):
        """
        Send a response to the first pending request, if there are no
        pending requests then queue the response up. It will fire when
        the next request is made

        An C{AssertionError} is raised if the entityType and request don't
        match those for the pending request.
        """
        if self._pending_requests:
            request_info, response = self._pending_requests.pop(0)
            expected = (entityType, request)
            obtained = request_info[:2]
            assert expected == obtained, "Requests are different: %r != %r" % (
                obtained, expected)
            response.callback(content)
        else:
            self._queued_responses.append((entityType, request, content))

    def error(self, reason):
        """Send an error response to the first pending request."""
        if self._pending_requests:
            _, response = self._pending_requests.pop(0)
            response.errback(reason)
        else:
            self._queued_errors.append(reason)

    @property
    def transport(self):

        class Transport(object):
            loseConnection = self._loseConnection

        return Transport()

    def _loseConnection(self):
        self.connected = False
        for _, response in self._pending_requests:
            if not response.called:
                response.errback(ConnectionDone())
        self.disconnected.callback(None)


class StubCLI(object):

    def __init__(self, juju_home, fail=False):
        self._fail = fail
        self.called_fetch = False
        self.called_juju_status = False
        self.called_get_all_logs = False
        self.calls = []

    def fetch_file(self, *args, **kwargs):
        self.called_fetch = True
        self.calls.append(("fetch_file", args, kwargs))
        if self._fail:
            raise CLIError("Fetch failed", "ERROR: Fetch failed", code=1)
        return succeed("Success from FakeJujuProcess.fetch_file")

    def get_juju_status(self, *args, **kwargs):
        self.called_juju_status = True
        self.calls.append(("get_juju_status", args, kwargs))
        if self._fail:
            raise CLIError("Status failed", "ERROR: Status failed", code=1)
        return succeed("Success from FakeJujuProcess.get_juju_status")

    def get_all_logs(self, *args, **kwargs):
        self.called_get_all_logs = True
        self.calls.append(("get_all_logs", args, kwargs))
        if self._fail:
            raise CLIError("Logs failed", "ERROR: Logs failed", code=1)
        return succeed("Success from FakeJujuProcess.get_all_logs")


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
