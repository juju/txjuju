# Copyright 2016 Canonical Limited.  All rights reserved.

import unittest

import txjuju
from txjuju import process


class GetProcessClassTest(unittest.TestCase):

    def test_juju1(self):
        """Passing in c.juju.JUJU1 should result in Juju1Process."""
        cls = txjuju.get_process_class(txjuju.JUJU1)
        self.assertIs(cls, process.Juju1Process)

    def test_juju2(self):
        """Passing in c.juju.JUJU2 should result in Juju2Process."""
        cls = txjuju.get_process_class(txjuju.JUJU2)
        self.assertIs(cls, process.Juju2Process)

    def test_unsupported(self):
        """Passing in an unrecognized release should cause an error."""
        with self.assertRaises(ValueError):
            txjuju.get_process_class("<???>")
