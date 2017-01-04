# Copyright 2017 Canonical Limited.  All rights reserved.

import unittest

from twisted.logger import globalLogPublisher

from ..websockets import STATUSES
from ..websocketsclient import WebSocketsClientFactory, log_closed_connection


class WebSocketsClientFactorTest(unittest.TestCase):

    def test_is_not_noisy(self):
        """WebSocketsClientFactory is not noisy"""
        self.assertFalse(WebSocketsClientFactory.noisy)


class LogClosedConnectionTest(unittest.TestCase):

    def setUp(self):
        """Capture logs."""
        super(LogClosedConnectionTest, self).setUp()
        self.log_events = []
        globalLogPublisher.addObserver(self.log_events.append)
        self.addCleanup(
            globalLogPublisher.removeObserver, self.log_events.append)

    def test_no_log_for_normal(self):
        """There is no log emitted for normal connection closing."""
        log_closed_connection((STATUSES.NORMAL, None))
        self.assertEqual([], self.log_events)

    def test_log_for_abnormal(self):
        """Abnormal closing is logged."""
        log_closed_connection((STATUSES.ABNORMAL_CLOSE, "foo"))
        self.assertEqual(1, len(self.log_events))
        log_event = self.log_events[0]
        self.assertEqual(
            "Closing connection: {!r} ('foo')".format(STATUSES.ABNORMAL_CLOSE),
            log_event["log_text"])
