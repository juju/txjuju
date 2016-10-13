# Copyright 2016 Canonical Limited.  All rights reserved.

import os.path

import yaml

from . import _utils


class ConfigWriter(object):
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
                "type": cloud.driver,
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


class CLIHooks(object):

    CFGDIR_ENVVAR = "JUJU_DATA"

    def get_bootstrap_args(self, spec, to=None, cfgfile=None,
                           verbose=False, gui=False, autoupgrade=False):
        args = ["bootstrap"]
        if verbose:
            args += ["-v"]
        if to:
            args += ["--to", to]
        if not autoupgrade:
            args += ["--no-auto-upgrade"]
        if not gui:
            args += ["--no-gui"]
        if cfgfile:
            args += ["--config", cfgfile]
        args += [spec.driver, spec.name]
        return args

    def get_api_info_args(self, controller_name=None):
        args = ["show-controller", "--show-password", "--format=yaml"]
        if controller_name is not None:
            args += [controller_name]
        return args

    def parse_api_info(self, output, controller_name=None):
        data = yaml.load(output, _utils.UnicodeYamlLoader)
        if controller_name is None:
            if len(data) > 1:
                raise RuntimeError(
                    "got back {} results, expected 1".format(len(data)))
            _, data = data.popitem()
        else:
            data = data[controller_name]

        info = {
            "endpoints": data["details"]["api-endpoints"],
            "user": data["account"]["user"].rstrip("@local"),
            "password": data["account"]["password"],
            "model_uuid": None,  # This will be set below for each model.
            }
        infos = {None: info}  # Start with the non-model API info.
        for modelname, modelinfo in data["models"].items():
            # Strip off the "<user>@local/" part.
            modelname = modelname.rpartition("/")[2]
            infos[modelname] = dict(info, model_uuid=modelinfo["uuid"])
        return infos

    def get_destroy_controller_args(self, name=None, force=False):
        if force:
            args = ["kill-controller", "--yes"]
        else:
            args = ["destroy-controller", "--yes", "--destroy-all-models"]
        if name is not None:
            args += [name]
        return args
