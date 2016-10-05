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
    """The base test class for Config-related tests."""

    def setUp(self):
        super(_ConfigTest, self).setUp()
        self.cfgdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.cfgdir)
        super(_ConfigTest, self).tearDown()

    def assert_cfgfile(self, filename, expected):
        """Contents of the identified YAML file must match expected."""
        filename = os.path.join(self.cfgdir, filename)
        with open(filename) as cfgfile:
            data = yaml.load(cfgfile)
        self.assertEqual(data, expected)


class ConfigTest(_ConfigTest, unittest.TestCase):
    """Tests that are not specific to a Juju version."""

    # The version doesn't matter as long as it's consistent.
    version = "1.25.6"

    def populate_cfgdir(self, name):
        """Write a basic Juju config to self.cfgdir."""
        controller = ControllerConfig.from_info(
            name, "lxd", "my-lxd", "xenial", "pw")
        cfg = Config(controller)
        cfg.write(self.cfgdir, self.version)

    def test_write_cfgdir_missing(self):
        """Config.write() creates the config dir if it is missing."""
        cfgdir = os.path.join(self.cfgdir, "one", "two", "three")
        cfg = Config(ControllerConfig("eggs", CloudConfig("maas")))
        cfg.write(cfgdir, self.version, clobber=True)

        self.assertEqual(os.listdir(cfgdir), ["environments.yaml"])

    def test_write_clobber_collision(self):
        """Config.write() overwrites config files if clobber is True."""
        self.populate_cfgdir("spam")
        cfg = Config(ControllerConfig(
            "eggs", CloudConfig("maas"), BootstrapConfig("")))
        cfg.write(self.cfgdir, self.version, clobber=True)

        self.assert_cfgfile(
            "environments.yaml",
            {"environments": {"eggs": {"type": "maas"}}})

    def test_write_clobber_no_collision(self):
        """Config.write() behaves like normal if clobber is True and
        the config files aren't there already."""
        cfg = Config(ControllerConfig("eggs", CloudConfig("maas")))
        cfg.write(self.cfgdir, self.version, clobber=True)

        self.assertEqual(os.listdir(self.cfgdir), ["environments.yaml"])

    def test_write_no_clobber_collision(self):
        """Config.write() fails if clobber is False and the config files
        are already there.  The existing files are not changed."""
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
        """Config.write() works fine if clobber is False and no config
        files are already there."""
        cfg = Config(ControllerConfig("eggs", CloudConfig("maas")))
        cfg.write(self.cfgdir, self.version, clobber=False)

        self.assertEqual(os.listdir(self.cfgdir), ["environments.yaml"])


class ConfigTest_Juju1(_ConfigTest, unittest.TestCase):

    VERSION = "1.25.6"

    def test_write_one_full(self):
        """Config.write() works fine for Juju 1.x if there is only one
        fully-populated ControllerConfig."""
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
        """Config.write() works fine for Juju 1.x if there is only one
        partially-populated ControllerConfig."""
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
        """Config.write() works fine for Juju 1.x if there are multiple
        controller configs."""
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
        """Config.write() works fine for Juju 1.x if there aren't any
        controller configs."""
        cfg = Config()
        bootstraps = cfg.write(self.cfgdir, self.VERSION)

        self.assertIsNone(bootstraps)
        self.assertEqual(os.listdir(self.cfgdir), ["environments.yaml"])
        self.assert_cfgfile("environments.yaml", {})


class ConfigTest_Juju2(_ConfigTest, unittest.TestCase):

    VERSION = "2.0.0"

    def test_write_one_full(self):
        """Config.write() works fine for Juju 2.x if there is only one
        fully-populated ControllerConfig."""
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
        """Config.write() works fine for Juju 2.x if there is only one
        partially-populated ControllerConfig."""
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
        """Config.write() works fine for Juju 2.x if there are multiple
        controller configs."""
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
        """Config.write() works fine for Juju 2.x if there aren't any
        controller configs."""
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
