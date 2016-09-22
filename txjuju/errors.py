# Copyright 2016 Canonical Limited.  All rights reserved.


class CLIError(Exception):
    """Raised when juju fails."""

    def __init__(self, out, err, code=None, signal=None):
        if code is not None:
            reason = "exit code {}".format(code)
        if signal is not None:
            reason = "signal {}".format(signal)
        msg = "juju ended with {} (out='{}', err='{}')".format(reason, out, err)
        super(CLIError, self).__init__(msg)

        self.out = out
        self.err = err
        self.code = code
        self.signal = signal


class APIRequestError(Exception):
    """The server returned an error for a given API request."""

    def __init__(self, error, code):
        """
        @param error: The human-oriented error message.
        @param code: The machine-oriented error code (a string, see
            juju/apiserver/params/apierror.go).
        """
        msg = "{} (code: '{}')".format(error, code)
        super(APIRequestError, self).__init__(msg)
        self.error = error
        self.code = code


class APIAuthError(APIRequestError):
    """Authorization error (e.g. login request with to wrong password)."""


class APIRetriableError(APIRequestError):
    """A server-side error that could be retried (e.g. juju is upgrading)."""


class AllWatcherStoppedError(APIRetriableError):
    """The server stopped the AllWatcher (probably due to a tools upgrade)."""


class InvalidAPIEndpointAddress(Exception):
    """The address is an invalid Juju API endpoint.

    @param addr: The invalid address.
    @type addr: C{str}
    """

    def __init__(self, addr):
        msg = "Invalid Juju endpoint: {}".format(addr)
        super(InvalidAPIEndpointAddress, self).__init__(msg)
        self.addr = addr
