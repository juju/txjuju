# Copyright 2016 Canonical Limited.  All rights reserved.

"""Wire-level protocol for speaking to a Juju API server.

See http://bazaar.launchpad.net/~juju/juju-core/trunk/view/head:/doc/api.txt
"""

from json import dumps, loads

from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol, Factory
from twisted.web.client import readBody

from .errors import APIRequestError, APIAuthError, APIRetriableError


# Map known failures modes to the associated exception class.
# See https://github.com/juju/juju/blob/master/apiserver/params/apierror.go
ERROR_CODES = {
    "unauthorized access": APIAuthError,
    "upgrade in progress": APIRetriableError,
    "watcher was stopped": APIRetriableError,
    "try again": APIRetriableError,
    "excessive contention": APIRetriableError,
}


class APIClientProtocol(Protocol):
    """A client protocol that knows how to speak to a Juju API server.

    @ivar disconnected: A deferred fired when the connection drops.
    @type disconnected: C{Deferred}

    @ivar _outstandingRequests: Maps the IDs of outstanding requests
        to their deferreds. An outstanding request is a request that
        has been sent to the server but for which we didn't get a response
        yet. Multiple requests can be outstanding at a given time.
    @type _outstandingRequests: C{dict}

    @ivar _requestId: An integer which is used as ID when sending a
        new request and is increased by 1 each time.
    @type _requestId: C{int}
    """

    def __init__(self):
        self.disconnected = Deferred()
        self._outstandingRequests = {}
        self._requestId = 0

    def sendRequest(self, entityType, request, entityId=None, params=None,
                    facade_version=None):
        """Send a new API request to the server.

        @param entityType: The type of the entity this request is targeted to.
        @type entityType: str

        @param request: The action to perform on the target entity.
        @type request: str

        @param entityId: The specific ID of the target entity, or C{None} if
            the target entity is a singleton.
        @type entityId: str

        @param params: The key/value parameters for the action being performed.
        @type params: dict

        @param facade_version: Optional request API facade version. This is not
            the juju major version. Most API request types have an API facade
            version that differs based on what request you are performing.
            For example, the login facade supported in juju2 is version 3,
            the add machines facade supported is version 1. The absence of
            a facade_version is interpreted as 0 by both juju1 and juju2 API.
        @type facade_version: int
        """
        # Generate a non-outstanding request ID, by simply incrementing a mark
        self._requestId += 1

        # Build the request payload
        if params is None:
            params = {}
        payload = {"RequestId": self._requestId,
                   "Type": entityType,
                   "Request": request,
                   "Params": params}
        if entityId is not None:
            payload["Id"] = entityId
        if facade_version is not None:
            payload["Version"] = facade_version

        # Send the request payload as single JSON-encoded WebSocket message
        self.transport.write(dumps(payload))

        # Take note of this outstanding request
        deferred = Deferred()
        self._outstandingRequests[self._requestId] = deferred

        return deferred

    def connectionLost(self, reason):
        # Fail all outstanding requests
        deferreds = self._outstandingRequests.values()
        self._outstandingRequests.clear()
        for deferred in deferreds:
            deferred.errback(reason)
        self.disconnected.callback(None)

    def dataReceived(self, message):
        """Parse responses from the server and fire the relevant deferreds."""
        reqid, response, error = _parse_response(message)

        # Fire the deferred associated with this response.
        deferred = self._outstandingRequests.pop(reqid)
        if error is not None:
            deferred.errback(error)
        else:
            deferred.callback(response)


def parse_response(message):
    """Parse responses from the server and return the result."""
    _, response, error = _parse_response(message)
    if error is not None:
        raise error
    return response


def _parse_response(message):
    # Decode the JSON message
    payload = loads(message)

    reqid = payload.pop("RequestId")
    error = payload.pop("Error", None)
    if error is not None:
        # ErrorCode is present only for errors that support it, otherwise
        # it's an empty string that gets omitted by the payload (due to
        # the 'omitempty' annotation in the outMsg struct of
        # juju/rpc/jsoncodec/codec.go.
        code = payload.pop("ErrorCode", "")
        error_class = ERROR_CODES.get(code, APIRequestError)
        error = error_class(error, code)
    try:
        response = payload.pop("Response")
    except KeyError:
        response = payload
    return reqid, response, error


def handle_response(response):
    """Return the response body."""
    # TODO: fail if response.code != 200?
    d = readBody(response)
    d.addCallback(parse_response)
    return d


class APIClientFactory(Factory):
    """Build L{JujuProtocol} instances."""

    protocol = APIClientProtocol
