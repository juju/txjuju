# Copyright 2016 Canonical Limited.  All rights reserved.

import os.path

import yaml


class Writer(object):
    """The JujuConfig writer specific to Juju 2.x."""

    def filenames(self, controllers):
        """The filenames of the files which will be written."""
        filenames = ['clouds.yaml', 'credentials.yaml']
        for controller in controllers:
            filename = "bootstrap-{}.yaml".format(controller.name)
            filenames.append(filename)
        return filenames

    def write(self, controllers, cfgdir):
        """Write all configs to the given config directory."""
        configs = self._as_dicts(controllers)

        clouds_filename = os.path.join(cfgdir, "clouds.yaml")
        with open(clouds_filename, "w") as fd:
            config = {"clouds": configs["clouds"]}
            yaml.safe_dump(config, fd)

        credentials_filename = os.path.join(cfgdir, "credentials.yaml")
        with open(credentials_filename, "w") as fd:
            config = {"credentials": configs["credentials"]}
            yaml.safe_dump(config, fd)

        bootstrap_filenames = {}
        for name, config in configs["bootstrap"].items():
            filename = "bootstrap-{}.yaml".format(name)
            bootstrap_filename = os.path.join(cfgdir, filename)
            with open(bootstrap_filename, "w") as fd:
                yaml.safe_dump(config, fd)
            bootstrap_filenames[name] = bootstrap_filename

        return bootstrap_filenames

    def _as_dicts(self, controllers):
        """Return a YAML-serializable version of the config."""
        configs = {
            "clouds": {},
            "credentials": {},
            "bootstrap": {},
            }
        if not controllers:
            return configs
        clouds = configs["clouds"] = {}
        credentials = configs["credentials"] = {}
        bootstrap = configs["bootstrap"] = {}

        for controller in controllers:
            self._update_clouds(controller, clouds)
            self._update_credentials(controller, credentials)
            self._update_bootstrap(controller, bootstrap)
        return configs

    def _update_clouds(self, controller, clouds):
        """Update clouds for a single controller config.

        @param controller: A JujuControllerConfig to serialize for Juju 2.x.
        @param clouds: The serialized clouds config to update.
        """
        cloud = controller.cloud
        if cloud.name in clouds:
            # TODO What to do for duplicates?
            raise NotImplementedError
        else:
            config = {
                "type": cloud.type,
                }
            if cloud.endpoint:
                config["endpoint"] = str(cloud.endpoint)
            # TODO Add support for auth_types as soon as needed.
            clouds[cloud.name] = config

    def _update_credentials(self, controller, credentials):
        """Update credentials for a single controller config.

        @param controller: A JujuControllerConfig to serialize for Juju 2.x.
        @param credentials: The serialized credentials config to update.
        """
        if controller.cloud.credentials:
            # TODO Implement this once it's needed.
            raise NotImplementedError

    def _update_bootstrap(self, controller, bootstraps):
        """Update a bootstrap config for a single controller config.

        @param controller: A JujuControllerConfig to serialize for Juju 2.x.
        @param bootstrap: The serializable bootstrap config to update.
        """
        if controller.name in bootstraps:
            # TODO What to do for duplicates?
            raise NotImplementedError
        else:
            bootstrap = controller.bootstrap
            config = {}
            if bootstrap.default_series:
                config["default-series"] = bootstrap.default_series
            if bootstrap.admin_secret:
                # XXX admin-secret used to be passed as bootstrap parameters
                # but currently fails on juju2beta6.
                pass
            bootstraps[controller.name] = config
