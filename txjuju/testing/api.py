# Copyright 2016 Canonical Limited.  All rights reserved.

import json

from twisted.internet.error import ConnectionDone, ConnectionLost
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

from txjuju.protocol import APIClientProtocol


class FakeAPIBackend(object):
    """A fake transport for an APIClientProtocol.

    @ivar requests: Map request IDs to their payload.
    """

    def __init__(self, version="2.0.0"):
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
        if self.version.startswith("2."):
            api_servers = [
                [{"space-name": "net-%d" % index,
                  "port": 17070,
                  "scope": "local-cloud",
                  "type": "ipv4",
                  "value": endpoint}]
                for index, endpoint in enumerate(endpoints)]
            return self.response(
                {"model-tag": "model-uuid-xyz",
                 "servers": api_servers})
        else:
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

    def responseModelInfo(self, name, providertype):
        assert not self.version.startswith("1.")

        info = {"name": name,
                "provider-type": providertype,
                "default-series": "trusty",
                "uuid": "model-uuid-xyz",
                "controller-uuid": "controller-uuid-abc",
                }
        return self.response({"results": [{"result": info}]})

    def responseCloud(self, cloudtype):
        assert not self.version.startswith("1.")

        cloud = {"type": cloudtype,
                 "auth-types": [],
                 "endpoint": "",
                 "storage-endpoint": "",
                 "regions": [],
                 }
        return self.response({"results": [{"cloud": cloud}]})

    def responseWatchAll(self):
        if self.version.startswith("2."):
            self.response({"watcher-id": "1"})
        else:
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

        if self.version.startswith("2."):
            self.response({"deltas": responses})
        else:
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
        if self.version.startswith("2."):
            return ["annotation", verb, {
                "annotations": info.pairs,
                "tag": info.name}]
        else:
            return ["annotation", verb, {
                "Annotations": info.pairs,
                "Tag": info.name}]

    def _formatApplicationInfo(self, info, verb):
        if self.version.startswith("2."):
            return ["application", verb, {
                "name": info.name,
                "charm-url": info.charmURL}]
        else:
            return ["service", verb, {
                "Name": info.name,
                "CharmURL": info.charmURL}]

    def _formatUnitInfo(self, info, verb):
        if self.version.startswith("2."):
            return ["unit", verb, {
                "name": info.name,
                "application": info.applicationName,
                "charm-url": info.charmURL}]
        else:
            return ["unit", verb, {
                "Name": info.name,
                "Service": info.applicationName,
                "CharmURL": info.charmURL}]

    def _formatMachineInfo(self, info, verb):
        if self.version.startswith("2."):
            return ["machine", verb, {
                "id": info.id,
                "instance-id": info.instanceId,
                "agent-status": info.status}]
        else:
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
