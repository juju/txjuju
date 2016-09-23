# Copyright 2016 Canonical Limited.  All rights reserved.

import unittest

from txjuju.config import (
    ControllerConfig, CloudConfig, BootstrapConfig)


class ControllerConfigTest(unittest.TestCase):

    def test_from_info_full(self):
        cfg = ControllerConfig.from_info(
            u"spam", u"lxd", u"my-lxd", u"xenial", u"sekret")

        self.assertEqual(cfg.name, u"spam")
        self.assertEqual(cfg.cloud, CloudConfig(u"my-lxd", u"lxd"))
        self.assertEqual(cfg.bootstrap, BootstrapConfig(u"xenial", u"sekret"))

    def test_from_info_minimal(self):
        cfg = ControllerConfig.from_info(u"spam", u"lxd")

        self.assertEqual(cfg.name, u"spam")
        self.assertEqual(cfg.cloud, CloudConfig(u"spam-lxd", u"lxd"))
        self.assertEqual(cfg.bootstrap, BootstrapConfig(u"trusty"))

    def test_from_info_conversions(self):
        cfg = ControllerConfig.from_info(
            "spam", "lxd", "my-lxd", "xenial", "sekret")

        self.assertEqual(cfg.name, u"spam")

    def test_from_info_empty(self):
        cfg = ControllerConfig.from_info(u"spam", u"lxd", u"my-lxd", u"", u"")

        self.assertEqual(cfg.name, u"spam")
        self.assertEqual(cfg.cloud, CloudConfig(u"my-lxd", u"lxd"))
        self.assertEqual(cfg.bootstrap, BootstrapConfig(""))

    def test_from_info_missing_name(self):
        with self.assertRaises(ValueError):
            ControllerConfig.from_info(None, "lxd")
        with self.assertRaises(ValueError):
            ControllerConfig.from_info("", "lxd")

    def test_from_info_missing_type(self):
        with self.assertRaises(ValueError):
            ControllerConfig.from_info("spam", None)
        with self.assertRaises(ValueError):
            ControllerConfig.from_info("spam", "")

    def test_from_info_missing_cloud_name(self):
        with self.assertRaises(ValueError):
            ControllerConfig.from_info("spam", "lxd", "")

    def test_full(self):
        cloud = CloudConfig("my-lxd", "lxd", "https://localhost:8080")
        bootstrap = BootstrapConfig("xenial", "sekret")
        cfg = ControllerConfig(u"spam", cloud, bootstrap)

        self.assertEqual(cfg, (u"spam", cloud, bootstrap))

    def test_minimal(self):
        cloud = CloudConfig("lxd")
        cfg = ControllerConfig(u"spam", cloud)

        self.assertEqual(cfg, (u"spam", cloud, BootstrapConfig("")))

    def test_conversions(self):
        cloud = CloudConfig("lxd")
        bootstrap = BootstrapConfig("xenial")
        cfg = ControllerConfig("spam", cloud, bootstrap)

        self.assertEqual(cfg, (u"spam", cloud, bootstrap))

    def test_missing_name(self):
        cloud = CloudConfig("lxd")
        with self.assertRaises(ValueError):
            ControllerConfig(None, cloud)
        with self.assertRaises(ValueError):
            ControllerConfig("", cloud)

    def test_missing_cloud(self):
        with self.assertRaises(ValueError):
            ControllerConfig("spam", None)


class CloudConfigTest(unittest.TestCase):

    def test_full(self):
        cfg = CloudConfig(u"spam", u"lxd", u"localhost:8080", None, None)

        self.assertEqual(cfg.name, u"spam")
        self.assertEqual(cfg.type, u"lxd")
        self.assertEqual(cfg.endpoint, u"localhost:8080")
        self.assertIsNone(cfg.auth_types)
        self.assertIsNone(cfg.credentials)

    def test_minimal(self):
        cfg = CloudConfig(u"lxd")

        self.assertEqual(cfg.name, u"lxd")
        self.assertEqual(cfg.type, u"lxd")
        self.assertIsNone(cfg.endpoint)
        self.assertIsNone(cfg.auth_types)
        self.assertIsNone(cfg.credentials)

    def test_empty(self):
        cfg = CloudConfig(u"spam", u"lxd", u"")

        self.assertIsNone(cfg.endpoint)

    def test_conversions(self):
        cfg = CloudConfig("spam", "lxd", "localhost:8080")

        self.assertEqual(cfg.name, u"spam")
        self.assertEqual(cfg.type, u"lxd")
        self.assertEqual(cfg.endpoint, u"localhost:8080")
        self.assertIsNone(cfg.auth_types)
        self.assertIsNone(cfg.credentials)

    def test_missing_name(self):
        with self.assertRaises(ValueError):
            CloudConfig(None, "lxd")
        with self.assertRaises(ValueError):
            CloudConfig("", "lxd")

    def test_missing_type(self):
        with self.assertRaises(ValueError):
            CloudConfig("spam", "")

    def test_has_auth_types(self):
        with self.assertRaises(NotImplementedError):
            CloudConfig("spam", "lxd", "localhost", ["x"])

    def test_has_credentials(self):
        with self.assertRaises(NotImplementedError):
            CloudConfig("spam", "lxd", "localhost", None, ["x"])


class BootstrapConfigTest(unittest.TestCase):

    def test_full(self):
        cfg = BootstrapConfig(u"xenial", u"sekret")

        self.assertEqual(cfg.default_series, u"xenial")
        self.assertEqual(cfg.admin_secret, u"sekret")

    def test_minimal(self):
        cfg = BootstrapConfig()

        self.assertEqual(cfg.default_series, u"trusty")
        self.assertIsNone(cfg.admin_secret)

    def test_conversions(self):
        cfg = BootstrapConfig("xenial", "sekret")

        self.assertIsInstance(cfg.default_series, unicode)
        self.assertIsInstance(cfg.admin_secret, unicode)
