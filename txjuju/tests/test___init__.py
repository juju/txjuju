# Copyright 2016 Canonical Limited.  All rights reserved.

import unittest

import txjuju
from txjuju import cli


class GetCLIClassTest(unittest.TestCase):

    def test_juju1(self):
        """Passing in c.juju.JUJU1 should result in Juju1CLI."""
        cls = txjuju.get_cli_class(txjuju.JUJU1)
        self.assertIs(cls, cli.Juju1CLI)

    def test_juju2(self):
        """Passing in c.juju.JUJU2 should result in Juju2CLI."""
        cls = txjuju.get_cli_class(txjuju.JUJU2)
        self.assertIs(cls, cli.Juju2CLI)

    def test_unsupported(self):
        """Passing in an unrecognized release should cause an error."""
        with self.assertRaises(ValueError):
            txjuju.get_cli_class("<???>")
