# Copyright 2016 Canonical Limited.  All rights reserved.

from collections import namedtuple


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
        return super(BootstrapConfig, cls).__new__(
            default_series, admin_secret)
