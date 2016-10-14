# Copyright 2016 Canonical Limited.  All rights reserved.

import json
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
            "type": env.cloud.driver,
            }
        if env.bootstrap.default_series:
            config["default-series"] = env.bootstrap.default_series
        if env.bootstrap.admin_secret:
            config["admin-secret"] = env.bootstrap.admin_secret
        return config


class CLIHooks(object):

    CFGDIR_ENVVAR = "JUJU_HOME"

    def get_bootstrap_args(self, spec, to=None, cfgfile=None,
                           verbose=False, gui=False, autoupgrade=False):
        # Note that for Juju 1.x we ignore gui.
        if cfgfile is not None:
            raise ValueError("cfgfile not supported for Juju 1.x bootstrap")
        args = ["bootstrap"]
        if verbose:
            args += ["-v"]
        if to:
            args += ["--to", to]
        if not autoupgrade:
            args += ["--no-auto-upgrade"]
        args += ["-e", spec.name]
        return args

    def get_api_info_args(self, controller_name=None):
        args = ["api-info", "--password", "--refresh", "--format=json"]
        if controller_name is not None:
            args += ["-e", controller_name]
        return args

    def parse_api_info(self, output, controller_name=None):
        # Note that for Juju 1.x we ignore controller_name.
        data = json.loads(output)
        info = {
            "endpoints": data["state-servers"],
            "user": data["user"],
            "password": data["password"],
            "model_uuid": None,
            }
        return {
            None: info,
            "controller": dict(info, model_uuid=data["environ-uuid"]),
            }

    def get_destroy_controller_args(self, name=None, force=False):
        args = ["destroy-environment", "--yes"]
        if force:
            args += ["--force"]
        if name is not None:
            args += [name]
        return args
