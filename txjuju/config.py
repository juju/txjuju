# Copyright 2016 Canonical Limited.  All rights reserved.

from collections import namedtuple
import os
import os.path

from . import _config1, _config2


class Config(object):
    """An encapsulation of Juju's local configuration."""

    def __init__(self, *controllers):
        """
        @param controllers: The ControllerConfig for each of the
            controllers in the local configuration.
        """
        self._controllers = controllers

    def write(self, cfgdir, version, clobber=False):
        """Save the config to disk.

        How this happens is version-specific.

        @param cfgdir: The "juju home" directory where config files
            are stored.
        @param version: The Juju version to target.
        @param clobber: Allow the config's files to already exist.

        The filenames of the bootstrap configs are returned.  If the
        Juju version doesn't use a bootstrap config then this returns
        None.
        """
        if version.startswith("1."):
            writer = _config1.Writer()
        elif version.startswith("2."):
            writer = _config2.Writer()
        else:
            raise RuntimeError("unsupported Juju version {!r}".format(version))

        if clobber:
            filenames = writer.filenames(self._controllers)
            _prepare_cfgdir(cfgdir, filenames)
        else:
            _prepare_cfgdir(cfgdir)

        return writer.write(self._controllers, cfgdir)


class ControllerConfig(
        namedtuple("ControllerConfig",
                   "name type cloud_name default_series admin_secret")):
    """An encapsulation of the local configuration for a single controller."""

    DEFAULT_SERIES = "trusty"

    def __new__(cls, name, type,
                cloud_name=None, default_series=None, admin_secret=None):
        """
        @param name: The name of the controller.
        @param type: The controller's provider type.
        @param cloud_name: The name of the cloud (defaults to <name>-<type>).
        @param default_series: The OS series to provision by default.
            If not provided, it defaults to trusty.
        @param admin_secret: The password to use for the admin user,
            if any.
        """
        if cloud_name is None:
            cloud_name = "{}-{}".format(name, type)
        if default_series is None:
            default_series = cls.DEFAULT_SERIES
        return super(ControllerConfig, cls).__new__(
            cls, name, type, cloud_name, default_series, admin_secret)

    def __init__(self, *args, **kwargs):
        super(ControllerConfig, self).__init__(*args, **kwargs)
        if not self.name:
            raise ValueError("missing name")
        if not self.type:
            raise ValueError("missing type")
        if not self.cloud_name:
            raise ValueError("missing cloud_name")

    @property
    def cloud(self):
        """The CloudConfig for this controller config."""
        # TODO Sort these out as soon as we need them.
        endpoint = auth_types = credentials = None
        return CloudConfig(
            self.cloud_name, self.type, endpoint, auth_types, credentials)

    @property
    def bootstrap(self):
        """The BootstrapConfig for this controller config."""
        return BootstrapConfig(self.default_series, self.admin_secret)


class CloudConfig(
        namedtuple("CloudConfig",
                   "name type endpoint auth_types credentials")):
    """An encapsulation of the local config for a single cloud."""

    def __new__(cls, name, type,
                endpoint=None, auth_types=None, credentials=None):
        """
        @param name: The cloud's user-defined ID.
        @param type: The provider type.
        @param endpoint: The endpoint to use, if needed.
        @param auth_types: The set of supported auth types, if needed.
        @param credentials: The set of credentials configured
            for this cloud, if any.
        """
        # TODO Add provider-specific abstractions to support this.
        # TODO Add support for auth_types and credentials as soon as needed.
        return super(CloudConfig, cls).__new__(
            cls, name, type, endpoint, auth_types, credentials)

    def __init__(self, *args, **kwargs):
        super(CloudConfig, self).__init__(*args, **kwargs)
        if not self.name:
            raise ValueError("missing name")
        if not self.type:
            raise ValueError("missing type")
        # TODO Add support for auth_types and credentials as soon as needed.
        if self.auth_types is not None or self.credentials is not None:
            raise NotImplementedError


# TODO Implement CloudCredentialConfig as soon as needed.


class BootstrapConfig(
        namedtuple("BootstrapConfig", "default_series admin_secret")):
    """An encapsulation of a bootstrap config."""

    DEFAULT_SERIES = "trusty"

    def __new__(cls, default_series=None, admin_secret=None):
        """
        @param default_series: The OS series to provision by default.
            If not provided, it defaults to trusty.
        @param admin_secret: The password to use for the admin user,
            if any.
        """
        if default_series is None:
            default_series = cls.DEFAULT_SERIES
        return super(BootstrapConfig, cls).__new__(
            default_series, admin_secret)


def _prepare_cfgdir(cfgdir, protect_filenames=None):
    """Create the config directory, if necessary.

    @param cfgdir: The "juju home" directory where config files
        are stored.
    @param protect_filenames: The files that should not be clobbered.
    """
    if not os.path.exists(cfgdir):
        os.makedirs(cfgdir)
        return

    for filename in protect_filenames or ():
        filename = os.path.join(cfgdir, filename)
        if os.path.exists(filename):
            msg = "config file {!r} already exists".format(filename)
            raise RuntimeError(msg)
