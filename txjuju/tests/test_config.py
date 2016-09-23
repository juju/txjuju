# Copyright 2016 Canonical Limited.  All rights reserved.

import os
import os.path
import shutil
import tempfile
import unittest

import yaml

from txjuju.config import (
    Config, ControllerConfig, CloudConfig, BootstrapConfig)


class _ConfigTest(object):

    def setUp(self):
        super(_ConfigTest, self).setUp()
        self.cfgdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.cfgdir)
        super(_ConfigTest, self).tearDown()

    def assert_cfgfile(self, filename, expected):
        filename = os.path.join(self.cfgdir, filename)
        with open(filename) as cfgfile:
            data = yaml.load(cfgfile)
        self.assertEqual(data, expected)


class ConfigTest(_ConfigTest, unittest.TestCase):

    # The version doesn't matter as long as it's consistent.
    version = "1.25.6"

    def populate_cfgdir(self, name):
        controller = ControllerConfig.from_info(
            name, "lxd", "my-lxd", "xenial", "pw")
        cfg = Config(controller)
        cfg.write(self.cfgdir, self.version)

    def test_write_cfgdir_missing(self):
        cfgdir = os.path.join(self.cfgdir, "one", "two", "three")
        cfg = Config(ControllerConfig("eggs", CloudConfig("maas")))
        cfg.write(cfgdir, self.version, clobber=True)

        self.assertEqual(os.listdir(cfgdir), ["environments.yaml"])

    def test_write_clobber_collision(self):
        self.populate_cfgdir("spam")
        cfg = Config(ControllerConfig(
            "eggs", CloudConfig("maas"), BootstrapConfig("")))
        cfg.write(self.cfgdir, self.version, clobber=True)

        self.assert_cfgfile(
            "environments.yaml",
            {"environments": {"eggs": {"type": "maas"}}})

    def test_write_clobber_no_collision(self):
        cfg = Config(ControllerConfig("eggs", CloudConfig("maas")))
        cfg.write(self.cfgdir, self.version, clobber=True)

        self.assertEqual(os.listdir(self.cfgdir), ["environments.yaml"])

    def test_write_no_clobber_collision(self):
        self.populate_cfgdir("spam")
        cfg = Config(ControllerConfig("eggs", CloudConfig("maas")))

        with self.assertRaises(RuntimeError):
            cfg.write(self.cfgdir, self.version, clobber=False)
        self.assert_cfgfile(
            "environments.yaml",
            {"environments": {
                "spam": {
                    "type": "lxd",
                    "default-series": "xenial",
                    "admin-secret": "pw",
                    }
                }
             })

    def test_write_no_clobber_no_collision(self):
        cfg = Config(ControllerConfig("eggs", CloudConfig("maas")))
        cfg.write(self.cfgdir, self.version, clobber=False)

        self.assertEqual(os.listdir(self.cfgdir), ["environments.yaml"])


class ConfigTest_Juju1(_ConfigTest, unittest.TestCase):

    VERSION = "1.25.6"

    def test_write_one_full(self):
        cfg = Config(ControllerConfig.from_info(
            "spam", "lxd", "my-lxd", "xenial", "pw"))
        bootstraps = cfg.write(self.cfgdir, self.VERSION)

        self.assertIsNone(bootstraps)
        self.assertEqual(os.listdir(self.cfgdir), ["environments.yaml"])
        self.assert_cfgfile(
            "environments.yaml",
            {"environments": {
                "spam": {
                    "type": "lxd",
                    "default-series": "xenial",
                    "admin-secret": "pw",
                    }
                }
             })

    def test_write_one_minimal(self):
        cfg = Config(
            ControllerConfig.from_info("spam", "lxd", "my-lxd", "", ""))
        bootstraps = cfg.write(self.cfgdir, self.VERSION)

        self.assertIsNone(bootstraps)
        self.assertEqual(os.listdir(self.cfgdir), ["environments.yaml"])
        self.assert_cfgfile(
            "environments.yaml",
            {"environments": {
                "spam": {
                    "type": "lxd",
                    }
                }
             })

    def test_write_multiple(self):
        cfg = Config(
            ControllerConfig.from_info(
                "spam", "lxd", "my-lxd", "xenial", "sekret"),
            ControllerConfig.from_info(
                "eggs", "maas", "maas", "trusty", "pw"),
            )
        bootstraps = cfg.write(self.cfgdir, self.VERSION)

        self.assertIsNone(bootstraps)
        self.assertEqual(os.listdir(self.cfgdir), ["environments.yaml"])
        self.assert_cfgfile(
            "environments.yaml",
            {"environments": {
                "spam": {
                    "type": "lxd",
                    "default-series": "xenial",
                    "admin-secret": "sekret",
                    },
                "eggs": {
                    "type": "maas",
                    "default-series": "trusty",
                    "admin-secret": "pw",
                    }
                }
             })

    def test_write_none(self):
        cfg = Config()
        bootstraps = cfg.write(self.cfgdir, self.VERSION)

        self.assertIsNone(bootstraps)
        self.assertEqual(os.listdir(self.cfgdir), ["environments.yaml"])
        self.assert_cfgfile("environments.yaml", {})


class ConfigTest_Juju2(_ConfigTest, unittest.TestCase):

    VERSION = "2.0.0"

    def test_write_one_full(self):
        cfg = Config(ControllerConfig.from_info(
            "spam", "lxd", "my-lxd", "xenial", "pw"))
        bootstraps = cfg.write(self.cfgdir, self.VERSION)

        self.assertEquals(
            bootstraps,
            {"spam": os.path.join(self.cfgdir, "bootstrap-spam.yaml"),
             })
        self.assertEqual(
            sorted(os.listdir(self.cfgdir)),
            ["bootstrap-spam.yaml",
             "clouds.yaml",
             "credentials.yaml",
             ])
        self.assert_cfgfile(
            "bootstrap-spam.yaml",
            {"default-series": "xenial",
             })
        self.assert_cfgfile(
            "clouds.yaml",
            {"clouds": {"my-lxd": {
                "type": "lxd",
                }}})
        self.assert_cfgfile("credentials.yaml", {"credentials": {}})

    def test_write_one_minimal(self):
        cfg = Config(ControllerConfig.from_info(
            "spam", "lxd", "my-lxd", "", ""))
        bootstraps = cfg.write(self.cfgdir, self.VERSION)

        self.assertEquals(
            bootstraps,
            {"spam": os.path.join(self.cfgdir, "bootstrap-spam.yaml"),
             })
        self.assertEqual(
            sorted(os.listdir(self.cfgdir)),
            ["bootstrap-spam.yaml",
             "clouds.yaml",
             "credentials.yaml",
             ])
        self.assert_cfgfile("bootstrap-spam.yaml", {})
        self.assert_cfgfile(
            "clouds.yaml",
            {"clouds": {"my-lxd": {
                "type": "lxd",
                }}})
        self.assert_cfgfile("credentials.yaml", {"credentials": {}})

    def test_write_multiple(self):
        cfg = Config(
            ControllerConfig.from_info(
                "spam", "lxd", "my-lxd", "xenial", "sekret"),
            ControllerConfig.from_info(
                "eggs", "maas", "maas", "trusty", "pw"),
            )
        bootstraps = cfg.write(self.cfgdir, self.VERSION)

        self.assertEquals(
            bootstraps,
            {"spam": os.path.join(self.cfgdir, "bootstrap-spam.yaml"),
             "eggs": os.path.join(self.cfgdir, "bootstrap-eggs.yaml"),
             })
        self.assertEqual(
            sorted(os.listdir(self.cfgdir)),
            ["bootstrap-eggs.yaml",
             "bootstrap-spam.yaml",
             "clouds.yaml",
             "credentials.yaml",
             ])
        self.assert_cfgfile(
            "bootstrap-eggs.yaml",
            {"default-series": "trusty",
             })
        self.assert_cfgfile(
            "bootstrap-spam.yaml",
            {"default-series": "xenial",
             })
        self.assert_cfgfile(
            "clouds.yaml",
            {"clouds": {
                "my-lxd": {
                    "type": "lxd",
                    },
                "maas": {
                    "type": "maas",
                    },
                },
             })
        self.assert_cfgfile("credentials.yaml", {"credentials": {}})

    def test_write_none(self):
        cfg = Config()
        bootstraps = cfg.write(self.cfgdir, self.VERSION)

        self.assertEqual(bootstraps, {})
        self.assertEqual(
            sorted(os.listdir(self.cfgdir)),
            ["clouds.yaml", "credentials.yaml"],
            )
        self.assert_cfgfile("clouds.yaml", {"clouds": {}})
        self.assert_cfgfile("credentials.yaml", {"credentials": {}})


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
