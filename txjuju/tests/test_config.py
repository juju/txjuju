# Copyright 2016 Canonical Limited.  All rights reserved.

import unittest

from txjuju.config import (
    ControllerConfig, CloudConfig, BootstrapConfig)


class ControllerConfigTest(unittest.TestCase):

    def test_from_info_full(self):
        """ControllerConfig.from_info() works when given all args."""
        cfg = ControllerConfig.from_info(
            u"spam", u"lxd", u"my-lxd", u"xenial", u"sekret")

        self.assertEqual(cfg.name, u"spam")
        self.assertEqual(cfg.cloud, CloudConfig(u"my-lxd", u"lxd"))
        self.assertEqual(cfg.bootstrap, BootstrapConfig(u"xenial", u"sekret"))

    def test_from_info_minimal(self):
        """ControllerConfig.from_info() works when given minimal args."""
        cfg = ControllerConfig.from_info(u"spam", u"lxd")

        self.assertEqual(cfg.name, u"spam")
        self.assertEqual(cfg.cloud, CloudConfig(u"spam-lxd", u"lxd"))
        self.assertEqual(cfg.bootstrap, BootstrapConfig(u"trusty"))

    def test_from_info_conversions(self):
        """ControllerConfig.from_info() converts str to unicode."""
        cfg = ControllerConfig.from_info(
            "spam", "lxd", "my-lxd", "xenial", "sekret")

        self.assertEqual(cfg.name, u"spam")
        # Testing the conversion of the other args is handled in the
        # tests for CloudConfig and BootstrapConfig.

    def test_from_info_empty(self):
        """ControllerConfig.from_info() still works when default_series
        and admin_secret are empty strings."""
        cfg = ControllerConfig.from_info(u"spam", u"lxd", u"my-lxd", u"", u"")

        self.assertEqual(cfg.name, u"spam")
        self.assertEqual(cfg.cloud, CloudConfig(u"my-lxd", u"lxd"))
        self.assertEqual(cfg.bootstrap, BootstrapConfig(""))

    def test_from_info_missing_name(self):
        """ControllerConfig.from_info() fails if name is None or empty."""
        with self.assertRaises(ValueError):
            ControllerConfig.from_info(None, "lxd")
        with self.assertRaises(ValueError):
            ControllerConfig.from_info("", "lxd")

    def test_from_info_missing_type(self):
        """ControllerConfig.from_info() fails if type is None or empty."""
        with self.assertRaises(ValueError):
            ControllerConfig.from_info("spam", None)
        with self.assertRaises(ValueError):
            ControllerConfig.from_info("spam", "")

    def test_from_info_missing_cloud_name(self):
        """ControllerConfig.from_info() fails if cloud_name is empty."""
        with self.assertRaises(ValueError):
            ControllerConfig.from_info("spam", "lxd", "")

    def test_full(self):
        """ControllerConfig() works when given all args."""
        cloud = CloudConfig("my-lxd", "lxd", "https://localhost:8080")
        bootstrap = BootstrapConfig("xenial", "sekret")
        cfg = ControllerConfig(u"spam", cloud, bootstrap)

        self.assertEqual(cfg, (u"spam", cloud, bootstrap))

    def test_minimal(self):
        """ControllerConfig() works when given minimal args ."""
        cloud = CloudConfig("lxd")
        cfg = ControllerConfig(u"spam", cloud)

        self.assertEqual(cfg, (u"spam", cloud, BootstrapConfig("")))

    def test_conversions(self):
        """ControllerConfig() converts str to unicode."""
        cloud = CloudConfig("lxd")
        bootstrap = BootstrapConfig("xenial")
        cfg = ControllerConfig("spam", cloud, bootstrap)

        self.assertEqual(cfg, (u"spam", cloud, bootstrap))

    def test_cloud_iterable(self):
        """ControllerConfig() supports cloud as an iterable."""
        cloud = CloudConfig("lxd")
        bootstrap = BootstrapConfig("xenial")
        cfg1 = ControllerConfig("spam", tuple(cloud), bootstrap)
        cfg2 = ControllerConfig("spam", list(cloud), bootstrap)

        self.assertEqual(cfg1.cloud, cloud)
        self.assertEqual(cfg2.cloud, cloud)

    def test_bootstrap_iterable(self):
        """ControllerConfig() supports bootstrap as an iterable."""
        cloud = CloudConfig("lxd")
        bootstrap = BootstrapConfig("xenial")
        cfg1 = ControllerConfig("spam", cloud, tuple(bootstrap))
        cfg2 = ControllerConfig("spam", cloud, list(bootstrap))

        self.assertEqual(cfg1.cloud, cloud)
        self.assertEqual(cfg2.cloud, cloud)

    def test_missing_name(self):
        """ControllerConfig() fails if name is None or empty."""
        cloud = CloudConfig("lxd")
        with self.assertRaises(ValueError):
            ControllerConfig(None, cloud)
        with self.assertRaises(ValueError):
            ControllerConfig("", cloud)

    def test_missing_cloud(self):
        """ControllerConfig() fails if cloud is None."""
        with self.assertRaises(ValueError):
            ControllerConfig("spam", None)

    def test_missing_bootstrap(self):
        """ControllerConfig() fails if bootstrap is empty."""
        with self.assertRaises(ValueError):
            ControllerConfig("spam", ())


class CloudConfigTest(unittest.TestCase):

    def test_full(self):
        """CloudConfig() works when given all args."""
        cfg = CloudConfig(u"spam", u"lxd", u"localhost:8080", None, None)

        self.assertEqual(cfg.name, u"spam")
        self.assertEqual(cfg.type, u"lxd")
        self.assertEqual(cfg.endpoint, u"localhost:8080")
        self.assertIsNone(cfg.auth_types)
        self.assertIsNone(cfg.credentials)

    def test_minimal(self):
        """CloudConfig() works when given minimal args."""
        cfg = CloudConfig(u"lxd")

        self.assertEqual(cfg.name, u"lxd")
        self.assertEqual(cfg.type, u"lxd")
        self.assertIsNone(cfg.endpoint)
        self.assertIsNone(cfg.auth_types)
        self.assertIsNone(cfg.credentials)

    def test_empty(self):
        """CloudConfig() still works when endpoint is empty."""
        cfg = CloudConfig(u"spam", u"lxd", u"")

        self.assertIsNone(cfg.endpoint)

    def test_conversions(self):
        """CloudConfig() converts str to unicode."""
        cfg = CloudConfig("spam", "lxd", "localhost:8080")

        self.assertEqual(cfg.name, u"spam")
        self.assertEqual(cfg.type, u"lxd")
        self.assertEqual(cfg.endpoint, u"localhost:8080")
        self.assertIsNone(cfg.auth_types)
        self.assertIsNone(cfg.credentials)

    def test_missing_name(self):
        """CloudConfig() fails when name is None or empty."""
        with self.assertRaises(ValueError):
            CloudConfig(None, "lxd")
        with self.assertRaises(ValueError):
            CloudConfig("", "lxd")

    def test_missing_type(self):
        """CloudConfig() fails when type is empty."""
        with self.assertRaises(ValueError):
            CloudConfig("spam", "")

    def test_has_auth_types(self):
        """CloudConfig() doesn't support auth_types yet."""
        with self.assertRaises(NotImplementedError):
            CloudConfig("spam", "lxd", "localhost", ["x"])

    def test_has_credentials(self):
        """CloudConfig() doesn't support credentials yet."""
        with self.assertRaises(NotImplementedError):
            CloudConfig("spam", "lxd", "localhost", None, ["x"])


class BootstrapConfigTest(unittest.TestCase):

    def test_full(self):
        """BootstrapConfig() works when given all args."""
        cfg = BootstrapConfig(u"xenial", u"sekret")

        self.assertEqual(cfg.default_series, u"xenial")
        self.assertEqual(cfg.admin_secret, u"sekret")

    def test_minimal(self):
        """BootstrapConfig() works when given no args."""
        cfg = BootstrapConfig()

        self.assertEqual(cfg.default_series, u"trusty")
        self.assertIsNone(cfg.admin_secret)

    def test_conversions(self):
        """BootstrapConfig() converts str to unicode."""
        cfg = BootstrapConfig("xenial", "sekret")

        self.assertIsInstance(cfg.default_series, unicode)
        self.assertIsInstance(cfg.admin_secret, unicode)
