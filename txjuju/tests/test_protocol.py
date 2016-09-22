# Copyright 2016 Canonical Limited.  All rights reserved.

from json import loads, dumps

from twisted.trial.unittest import TestCase
from twisted.internet.error import ConnectionDone

from txjuju.protocol import APIClientProtocol
from txjuju.errors import APIRequestError, APIRetriableError


class APIClientProtocolTest(TestCase):

    def setUp(self):
        super(APIClientProtocolTest, self).setUp()
        self.messages = []
        self.protocol = APIClientProtocol()

        class Transport(object):
            write = self.messages.append

        self.protocol.makeConnection(Transport())

    def test_sendRequest(self):
        """
        Sending a request results in a WebSocket message being sent, holding
        a JSON-encode payload with the request details.
        """
        self.protocol.sendRequest("Admin", "Login")
        [message] = self.messages
        self.assertEqual({"RequestId": 1,
                          "Type": "Admin",
                          "Request": "Login",
                          "Params": {}}, loads(message))

    def test_sendRequestWithVersion(self):
        """
        Sending a request with a version provided results in a WebSocket
        message being sent containing a Version parameter
        """
        self.protocol.sendRequest("Admin", "Login", facade_version=42)
        [message] = self.messages
        self.assertEqual({"RequestId": 1,
                          "Type": "Admin",
                          "Request": "Login",
                          "Version": 42,
                          "Params": {}}, loads(message))

    def test_sendRequestUniqueId(self):
        """
        A new request ID is generated each time.
        """
        self.protocol.sendRequest("Admin", "Login")
        self.protocol.sendRequest("Admin", "Login")
        [message1, message2] = self.messages
        self.assertEqual(1, loads(message1)["RequestId"])
        self.assertEqual(2, loads(message2)["RequestId"])

    def test_sendRequestParams(self):
        """
        If request parameters are provided, they are included in the payload.
        """
        params = {"AuthTag": "user-admin", "Passowrd": "xyzw"}
        self.protocol.sendRequest("Admin", "Login", params=params)
        [message] = self.messages
        self.assertEqual({"RequestId": 1,
                          "Type": "Admin",
                          "Request": "Login",
                          "Params": params}, loads(message))

    def test_sendRequestEntityID(self):
        """
        If a target entity ID is provided, it's included in the payload.
        """
        self.protocol.sendRequest("Machine", "Watch", entityId="99")
        [message] = self.messages
        self.assertEqual({"RequestId": 1,
                          "Type": "Machine",
                          "Id": "99",
                          "Request": "Watch",
                          "Params": {}}, loads(message))

    def test_dataReceived(self):
        """
        When the response for a certain response arrives, the associated
        deferred is fired with its result.
        """
        deferred = self.protocol.sendRequest("Machine", "Watch", entityId="99")
        response = {"RequestId": 1, "Response": {"WatcherId": "1"}}
        self.protocol.dataReceived(dumps(response))
        self.assertEqual({"WatcherId": "1"}, self.successResultOf(deferred))

    def test_dataReceivedNoResponseData(self):
        """
        If a response carries no data with it, then the associated deferred
        is fired with an empty C{dict}.
        """
        deferred = self.protocol.sendRequest("Admin", "Login")
        response = {"RequestId": 1}
        self.protocol.dataReceived(dumps(response))
        self.assertEqual({}, self.successResultOf(deferred))

    def test_dataReceivedWithError(self):
        """
        A response reports an error using the "Error" and "ErrorCode" keys,
        which are saved in the generated APIRequestError.
        """
        deferred = self.protocol.sendRequest("Admin", "Login")
        response = {
            "RequestId": 1,
            "Error": "juju failed",
            "ErrorCode": "some code"}
        self.protocol.dataReceived(dumps(response))
        failure = self.failureResultOf(deferred)
        failure.trap(APIRequestError)
        error = failure.value
        self.assertEqual("juju failed (code: 'some code')", error.message)
        self.assertEqual("some code", error.code)

    def test_dataReceivedKnownErrorCode(self):
        """
        If a response reports an error with a known error code, we raise
        the associated exception.
        """
        deferred = self.protocol.sendRequest("Admin", "Login")
        response = {
            "RequestId": 1,
            "Error": "upgrade in progress - Juju functionality is limited",
            "ErrorCode": "upgrade in progress"}
        self.protocol.dataReceived(dumps(response))
        failure = self.failureResultOf(deferred)
        failure.trap(APIRetriableError)
        self.assertEqual("upgrade in progress", failure.value.code)

    def test_dataReceivedNoErrorCode(self):
        """
        If a response reports an error without an error code, we default to
        empty string.
        """
        deferred = self.protocol.sendRequest("Admin", "Login")
        response = {
            "RequestId": 1,
            "Error": "upgrade in progress - Juju functionality is limited"}
        self.protocol.dataReceived(dumps(response))
        failure = self.failureResultOf(deferred)
        failure.trap(APIRequestError)
        self.assertEqual("", failure.value.code)

    def test_connectionLost(self):
        """
        If the connection is lost, all outstanding requests will errback.
        """
        deferred1 = self.protocol.sendRequest("Admin", "Login")
        deferred2 = self.protocol.sendRequest("Admin", "Login")
        self.protocol.connectionLost(ConnectionDone())
        failure1 = self.failureResultOf(deferred1)
        failure1.trap(ConnectionDone)
        failure2 = self.failureResultOf(deferred2)
        failure2.trap(ConnectionDone)
