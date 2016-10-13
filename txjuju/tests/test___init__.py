# Copyright 2016 Canonical Limited.  All rights reserved.

import os
import shutil
import tempfile
import unittest

import txjuju
from txjuju import cli


class GetCLIClassTests(unittest.TestCase):

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


class PrepareForBootstrapTests(unittest.TestCase):

    def setUp(self):
        super(PrepareForBootstrapTests, self).setUp()
        self.cfgdir = tempfile.mkdtemp(prefix="txjuju-test-")

    def tearDown(self):
        shutil.rmtree(self.cfgdir)
        super(PrepareForBootstrapTests, self).tearDown()

    def test_juju2(self):
        """
        prepare_for_bootstrap() for Juju 2.x results in no files.
        This may change in the future.
        """
        spec = cli.BootstrapSpec("spam", "lxd")
        version = "2.0.0"
        filename = txjuju.prepare_for_bootstrap(spec, version, self.cfgdir)

        self.assertIsNone(filename)
        self.assertEqual(os.listdir(self.cfgdir), [])

    def test_juju1(self):
        """
        prepare_for_bootstrap() for Juju 1.x results in
        an environments.yaml file.
        """
        spec = cli.BootstrapSpec("spam", "lxd")
        version = "1.25.6"
        filename = txjuju.prepare_for_bootstrap(spec, version, self.cfgdir)

        self.assertIsNone(filename)
        self.assertEqual(os.listdir(self.cfgdir), ["environments.yaml"])
