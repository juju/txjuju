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
            _prepare_cfgdir(cfgdir)
        else:
            filenames = writer.filenames(self._controllers)
            _prepare_cfgdir(cfgdir, filenames)

        return writer.write(self._controllers, cfgdir)


class ControllerConfig(
        namedtuple("ControllerConfig", "name cloud bootstrap")):
    """An encapsulation of the local configuration for a single controller."""

    DEFAULT_SERIES = "trusty"

    @classmethod
    def from_info(cls, name, type,
                  cloud_name=None, default_series=None, admin_secret=None):
        """Return a new controller config for the given info.

        All arguments must be values that juju will accept for the
        respective meaning (e.g. name -> an acceptable controller name).

        @param name: The name of the controller.
        @param type: The controller's provider type.
        @param cloud_name: The name of the cloud (defaults to <name>-<type>).
        @param default_series: The OS series to provision by default.
            If not provided, it defaults to trusty.
        @param admin_secret: The password to use for the admin user,
            if any.
        """
        if cloud_name is None and name and type:
            cloud_name = "{}-{}".format(name, type)
        # TODO Sort these out as soon as we need them.
        endpoint = auth_types = credentials = None
        return cls(
            name,
            (cloud_name, type, endpoint, auth_types, credentials),
            (default_series, admin_secret),
            )

    def __new__(cls, name, cloud, bootstrap=None):
        """
        @param name: The name of the controller.  It must be a name that
            juju will accept for a controller.
        @param cloud: The controller's cloud config (or the raw data
            to make one).
        @param bootstrap: The controller's bootstrap config (or the raw
            data to make one), if any.
        """
        name = unicode(name) if name else None

        if not isinstance(cloud, CloudConfig):
            cloud = CloudConfig(*cloud) if cloud else None

        if bootstrap is None:
            bootstrap = BootstrapConfig("")
        elif not isinstance(bootstrap, BootstrapConfig):
            bootstrap = BootstrapConfig(*bootstrap) if bootstrap else None

        return super(ControllerConfig, cls).__new__(
            cls, name, cloud, bootstrap)

    def __init__(self, *args, **kwargs):
        super(ControllerConfig, self).__init__(*args, **kwargs)
        if not self.name:
            raise ValueError("missing name")
        if not self.cloud:
            raise ValueError("missing cloud")
        if not self.bootstrap:
            raise ValueError("missing bootstrap")


class CloudConfig(
        namedtuple("CloudConfig",
                   "name type endpoint auth_types credentials")):
    """An encapsulation of the local config for a single cloud."""

    def __new__(cls, name, type=None, endpoint=None,
                auth_types=None, credentials=None):
        """
        All arguments must be values that juju will accept for the
        respective meaning (e.g. name -> an acceptable cloud name).

        @param name: The cloud's user-defined ID, e.g. "my-cloud".
        @param type: The provider type, e.g. lxd, maas
            (defaults to the name).
        @param endpoint: The endpoint to use, if needed,  Any URL or
            hostname is okay, as long as the provider supports it.
        @param auth_types: The set of supported auth types, if needed.
            <CURRENTLY NOT SUPPORTED>
        @param credentials: The set of credentials configured
            for this cloud, if any.
            <CURRENTLY NOT SUPPORTED>
        """
        name = unicode(name) if name else None
        if type is None:
            type = name
        type = unicode(type) if type else None
        endpoint = unicode(endpoint) if endpoint else None
        # TODO Add provider-specific abstractions to support auth_types?
        # TODO Add support for auth_types and credentials as soon as needed.
        auth_types = tuple(auth_types) if auth_types else None
        credentials = tuple(credentials) if credentials else None
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
        All arguments must be values that juju will accept for the
        respective meaning.

        @param default_series: The OS series to provision by default.
            If not provided, it defaults to trusty.
        @param admin_secret: The password to use for the admin user,
            if any.
        """
        if default_series is None:
            default_series = cls.DEFAULT_SERIES
        default_series = unicode(default_series) if default_series else None
        admin_secret = unicode(admin_secret) if admin_secret else None
        return super(BootstrapConfig, cls).__new__(
            cls, default_series, admin_secret)


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
