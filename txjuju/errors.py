# Copyright 2016 Canonical Limited.  All rights reserved.


class RequestError(Exception):
    """The server returned an error for a given API request."""

    def __init__(self, error, code):
        """
        @param error: The human-oriented error message.
        @param code: The machine-oriented error code (a string, see
            juju/apiserver/params/apierror.go).
        """
        super(RequestError, self).__init__("%s (code: '%s')" % (error, code))
        self.error = error
        self.code = code


class AuthError(RequestError):
    """Authorization error (e.g. login request with to wrong password)."""


class RetriableError(RequestError):
    """A server-side error that could be retried (e.g. juju is upgrading)."""


class AllWatcherStoppedError(RetriableError):
    """The server stopped the AllWatcher (probably due to a tools upgrade)."""


class InvalidEndpointAddress(Exception):
    """The address is an invalid Juju API endpoint.

    @param addr: The invalid address.
    @type addr: C{str}
    """

    def __init__(self, addr):
        super(InvalidEndpointAddress, self).__init__(
            "Invalid Juju endpoint: %s" % addr)
        self.addr = addr
