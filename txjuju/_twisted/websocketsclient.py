# Copyright 2016 Canonical Limited.  All rights reserved.

"""
The WebSockets client protocol (RFC 6455), provided as a protocol that knows
how to perform the opening handshake.

Example::

  def protocolReady(protocol):
      protocol.sendMessage("hello")

  factory = WebSocketsClientFactory()
  factory.deferred.addCallback(protocolReady)

  connectWebSockets(reactor, "ws://localhost:8000/", factory)
"""
from urlparse import urlparse

from twisted.python import log
from twisted.python.randbytes import secureRandom
from twisted.python.failure import Failure
from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ClientEndpoint, SSL4ClientEndpoint
from twisted.internet.defer import Deferred
from twisted.internet.error import TimeoutError
from twisted.web._newclient import HTTPClientParser, Request, ResponseFailed
from twisted.web.http_headers import Headers
from twisted.web.error import SchemeNotSupported


from .websockets import (
    WebSocketsProtocol, CONTROLS, _parseFrames, _makeFrame, _makeAccept,
    WebSocketsProtocolWrapper, WebSocketsTransport)


# default service ports for WebSocket URI schemas
DEFAULT_SCHEME_PORTS = {"ws": 80, "wss": 443}


class _FrameParser(WebSocketsProtocol):
    """Overrides Twisted's C{WebScoketProtocol} to parse client frames.

    Frames received by the client don't need to be checked using the
    mask. Hopefully these changes will eventually be incorporated in
    the branch attached to this ticket (which at the moment only supports
    server-side websocket connections):

    http://twistedmatrix.com/trac/ticket/4173

    At that point this wrapper can be dropped.
    """

    def _parseFrames(self):
        # Verbatim copy of the parent class logic, except that we don't need
        # a mask for _parseFrames if we are a client. Unfortunately there's
        # no hook to customize just this bit.
        needMask = not self.isClient
        for opcode, data, fin in _parseFrames(self._buffer, needMask=needMask):
            self._receiver.frameReceived(opcode, data, fin)
            if opcode == CONTROLS.CLOSE:
                # The other side wants us to close.
                code, reason = data
                msgFormat = "Closing connection: %(code)r"
                if reason:
                    msgFormat += " (%(reason)r)"
                log.msg(format=msgFormat, reason=reason, code=code)

                # Close the connection.
                self.transport.loseConnection()
                return
            elif opcode == CONTROLS.PING:
                # 5.5.2 PINGs must be responded to with PONGs.
                # 5.5.3 PONGs must contain the data that was sent with the
                # provoking PING.
                self.transport.write(_makeFrame(data, CONTROLS.PONG, True))


class _FrameSender(WebSocketsTransport):

    def sendFrame(self, opcode, data, fin):
        """
        Build a frame packet and send it over the wire, using a random
        frame mask.
        """
        mask = secureRandom(4)
        packet = _makeFrame(data, opcode, fin, mask=mask)
        self._transport.write(packet)


class HandshakeError(Exception):
    """Base class for WebSocket client handshake errors."""


class HandshakeProtocolError(HandshakeError):
    """The server sent a mangled HTTP response.

    @ivar error: An instance of C{twisted.web._newclient.ResponseFailed} with
        details about the specific HTTP protocol error.
    @type error: C{twisted.web._newclient.ResponseFailed}
    """
    def __init__(self, error):
        self.error = error


class HandshakeWrongStatus(HandshakeError):
    """The server replied with a HTTP status code other than 101.

    @ivar code: The HTTP status code received.
    @type code: C{int}
    """
    def __init__(self, code):
        self.code = code


class HandshakeWrongAcceptKey(HandshakeError):
    """The server replied with a wrong accept key.

    @ivar key: The Sec-WebSocket-Key header value sent by the client.
    @type type: C{string}

    @ivar key: The Sec-WebSocket-Accept header value received from the server.
    @type type: C{string}
    """
    def __init__(self, key, accept):
        self.key = key
        self.accept = accept


class Handshake(object):
    """Hold parmeters to be sent during the opening handshake HTTP request.

    @ivar key: A randomly generated handshake key, it will end up in
        the 'Sec-WebSocket-Key' header of the request.
    @type key: C{str}
    """

    def __init__(self, host, path, origin=None, protocol=None):
        """
        @param host: The target host, will end up in the 'Host' header.
        @type host: C{str}

        @ivar param: The target endpoint on the host, will end up as path
            in the 'GET' line of the request.
        @type path: C{str}

        @param origin: Where the request is coming from, will end up in
            the 'Origin' header (optional).
        @type origin: C{str}

        @ivar protocol: Application-level protocols acceptable to the client,
            will end up in the 'Sec-WebSocket-Protocol' header.
        @type protocol: C{list}
        """
        self.host = host
        self.path = path
        self.origin = origin
        self.protocol = protocol
        self.key = secureRandom(16).encode("base64").strip()

    def buildRequest(self):
        """Build the HTTP request used to start this handshake."""
        # Required headers
        headers = {"Host": [self.host],
                   "Upgrade": ["WebSocket"],
                   "Connection": ["Upgrade"],
                   "Sec-WebSocket-Key": [self.key],
                   "Sec-WebSocket-Version": ["13"]}

        # Optional headers
        if self.origin is not None:
            headers["Origin"] = [self.origin]
        if self.protocol is not None:
            headers["Sec-WebSocket-Protocol"] = self.protocol

        return Request("GET", self.path, Headers(headers),
                       bodyProducer=None, persistent=True)


class WebSocketsClientProtocol(WebSocketsProtocolWrapper, _FrameParser):
    """
    Client-side version of WebSocketsProtocolWrapper, performing the handshake.

    @ivar subProtocol: Once the handshake is complete, the sub-protocol that
        the server has indicated us (or C{None} if not specified).
    @type subProtocol: C{str}

    @ivar handshake: Must be set by the factory, see L{WebSocketsClientFactory}
    @type handshake: L{Handshake}.

    @ivar deferred: A deferred which will callback once the opening handshake
        has been successfully completed and the protocol is ready to send and
        receive frames, or errback with a the relevant failure otherwise. Must
        be set by the factory.
    @type deferred: C{twisted.internet.defer.Deferred}
    """
    isClient = True

    subProtocol = None
    handshake = None
    deferred = None

    _parser = None

    def connectionMade(self):
        self._buffer = []
        self._receiver.makeConnection(_FrameSender(self.transport))
        # Perform the handshake right after connecting.
        self.sendHandshake()

    def connectionLost(self, reason):
        if self._parser is not None:
            # This means we lost the connection before the handshake could
            # be complete, let's errback.
            self.deferred.errback(reason)
        else:
            # Forward the event to the user protocol
            self.wrappedProtocol.connectionLost(reason)

    def sendHandshake(self):
        """Perform a WebSocket opening handshake.

        The protocol will use the L{Handshake} parameters of the
        C{config} attribute of the factory.

        Once the handshake is complete, the C{deferred} attribute
        of the factory will be fired, either with C{None} (if the handshake
        was successful) or with a failure (if the handshake failed).
        """
        # The HTTP handshake request to send
        request = self.handshake.buildRequest()

        # We set a failing parser finisher because we take the transport
        # control back as soon as all response headers are received, so we
        # shouldn't ever deliver any data to the parser beside the headers.
        def finisher(_):
            raise RuntimeError("Parser cannot notify response finish")

        # From this point on all data we received will be forwarded to the
        # HTTP parser, see dataReceived,
        self._parser = HTTPClientParser(request, finisher)
        self._parser._responseDeferred.addCallback(self._handshakeResponse)
        self._parser._responseDeferred.addErrback(self._handshakeFailure)

        self._parser.makeConnection(self.transport)

        request.writeTo(self.transport)

    def handshakeMade(self):
        """Surrogate for connectionMade. Called after protocol negotiation."""
        self.wrappedProtocol.makeConnection(self)
        self.deferred.callback(self.wrappedProtocol)

    def abortHandshake(self, reason):
        """Abort the handshake, propagating the given error.

        @param reason: Details about the error.
        @type reason: L{twisted.python.Failure}
        """
        # Make sure we were performing the handshake
        assert self._parser is not None, "No handshake in progress"

        # This marks that the handshake has completed
        self._parser = None

        # Handshake errors are fatal, let's close the connection
        self.transport.abortConnection()
        self.deferred.errback(reason)

    def dataReceived(self, data):
        """
        Forward data to the HTTP parser if we are performing an handshake or
        process it as WebSocket payload otherwise.
        """
        if self._parser is not None:
            try:
                self._parser.dataReceived(data)
            except:
                # Disconnect the parser with the current failure, which will
                # cause the handshake deferred to errback.
                self._parser.connectionLost(Failure())
        else:
            WebSocketsProtocolWrapper.dataReceived(self, data)

    def _handshakeResponse(self, response):
        """
        Parse the HTTP response for the handshake request.
        """
        # Check the status code
        if response.code != 101:
            raise HandshakeWrongStatus(response.code)

        # Check the accept key
        accept = response.headers.getRawHeaders("Sec-WebSocket-Accept")
        if not accept or accept[0] != _makeAccept(self.handshake.key):
            raise HandshakeWrongAcceptKey(self.handshake.key, accept)

        # This marks that the handshake has completed
        self._parser = None

        # Figure out what protocol the server has chosen, if any
        protocol = response.headers.getRawHeaders("Sec-WebSocket-Protocol")
        if protocol:
            self.subProtocol = protocol[0]

        # The trasport was paused by the parser to avoid consuming non-header
        # data. Let's resume it.
        self.transport.resumeProducing()

        self.handshakeMade()

    def _handshakeFailure(self, failure):
        """
        Pass on the failure to L{abortHandshake}.
        """
        if failure.check(ResponseFailed):
            # The parser failed to parse the response, let's wrap it in
            # a HandshakeProtocolError
            failure = Failure(HandshakeProtocolError(failure.value))

        # Bail out in case of unexpected errors
        failure.trap(HandshakeError)

        self.abortHandshake(failure)

    def _parseFrames(self):
        _FrameParser._parseFrames(self)


class WebSocketsClientFactory(Factory):
    """Factory for building L{WebSocketsClientProtocol}s.

    @ivar handshake: An object holding the handshake parameters to send, it's
       initially C{None} and is expected to be set by user code by calling
       the C{setHandshake} method before connecting the factory.
    @type handshake: L{Handshake}.
    """
    protocol = WebSocketsClientProtocol
    handshake = None

    def setHandshake(self, handshake):
        """Set the L{Handshake} to use when sending the handshake request."""
        self.handshake = handshake

    def buildProtocol(self, addr):
        protocol = self.protocol(self.wrappedFactory.buildProtocol(addr))
        protocol.handshake = self.handshake
        protocol.deferred = Deferred()
        return protocol


class WebSocketsEndpoint(object):
    """Endpoint for connecting to a server over a WebSocket transport."""

    def __init__(self, reactor, uri, origin=None, protocol=None,
                 sslContextFactory=None, timeout=30):
        """
        @param reactor: The reactor to use for connecting.
        @type reactor: C{IReactor}

        @param uri: The URI of the endpoint (e.g. ws://for.com/bar)
        @type uri: str

        @param origin: The origin to use in the handshake request, if any.
        @type origin: str

        @param protocol: The protocol to use in the handshake, if any.
        @type protocol: str

        @param sslContextFactory: SSL Configuration information, if any.
        @type sslContextFactory: twisted.internet.ssl.ContextFactory

        @param timeout: The number of seconds to wait before assuming the
            connection has failed.
        @type timeout: int
        """
        segments = urlparse(uri)

        self._reactor = reactor
        self._host = segments.hostname
        self._port = segments.port or DEFAULT_SCHEME_PORTS.get(segments.scheme)
        self._scheme = segments.scheme
        self._handshake = Handshake(
            segments.hostname, segments.path, origin=origin, protocol=protocol)
        self._sslContextFactory = sslContextFactory
        self._timeout = timeout

    def connect(self, factory):
        """Connect with WebSocket over TCP or SSL."""
        websocketsFactory = WebSocketsClientFactory()
        websocketsFactory.setHandshake(self._handshake)
        websocketsFactory.wrappedFactory = factory
        endpoint = self._getEndpoint()
        deferred = endpoint.connect(websocketsFactory)
        protocolReference = []  # Trick to save a reference to the protocol

        def onConnectFailure(failure):
            # The connection failed (either due to an error or due to
            # the low-level endpoint timeout). Let's cancel our own
            # timeout and propagate the error.
            call.cancel()
            return failure

        def onConnectSuccess(protocol):
            # We're connected, now let's wait for the handshake
            protocolReference.append(protocol)
            return protocol.deferred.addBoth(onHandshakeFinished)

        def onHandshakeFinished(value):
            # The handshake has finished, either successfully or not. Unless
            # this is a timeout failure itself, let's cancel the timeout call.
            if not isinstance(value, Failure) or not value.check(TimeoutError):
                call.cancel()
            return value

        def onTimeout():
            # If we got here it means that the handshake has timed out, because
            # if the connection times out we cancel our own timeout (see
            # onConnectFailure). Let's abort the connection and errback.
            [protocol] = protocolReference
            protocol.abortHandshake(TimeoutError())

        call = self._reactor.callLater(self._timeout, onTimeout)

        deferred.addErrback(onConnectFailure)
        deferred.addCallback(onConnectSuccess)

        return deferred

    def _getEndpoint(self):
        """Return the endpoint to use for the underlying connection."""
        args = [self._reactor, self._host, self._port]
        if self._scheme == "ws":
            endpointClass = TCP4ClientEndpoint
        elif self._scheme == "wss":
            endpointClass = SSL4ClientEndpoint
            args.append(self._sslContextFactory)
        else:
            raise SchemeNotSupported("Unsupported scheme: %r" % self._scheme)
        return endpointClass(*args, timeout=self._timeout)
