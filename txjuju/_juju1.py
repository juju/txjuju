# Copyright 2016 Canonical Limited.  All rights reserved.

import os.path

import yaml


class ConfigWriter(object):
    """The JujuConfig writer specific to Juju 1.x."""

    def filenames(self, controllers):
        """The filenames of the files which will be written."""
        return ['environments.yaml']

    def write(self, controllers, cfgdir):
        """Write all configs to the given config directory."""
        config = self._as_dict(controllers)

        envsfile = os.path.join(cfgdir, "environments.yaml")
        with open(envsfile, "w") as fd:
            yaml.safe_dump(config, fd)

        # Juju 1.x doesn't use a bootstrap config so we do not return
        # a filename to one.
        return None

    def _as_dict(self, envs):
        """Return a YAML-serializable version of the config."""
        if not envs:
            return {}

        config = {
            "environments": {env.name: self._env_as_dict(env)
                             for env in envs},
            }
        return config

    def _env_as_dict(self, env):
        """Serialize the config for a single environment.

        @param env: A JujuControllerConfig to serialize for Juju 1.x.
        """
        config = {
            "type": env.cloud.type,
            }
        if env.bootstrap.default_series:
            config["default-series"] = env.bootstrap.default_series
        if env.bootstrap.admin_secret:
            config["admin-secret"] = env.bootstrap.admin_secret
        return config
