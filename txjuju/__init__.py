# Copyright 2016 Canonical Limited.  All rights reserved.

from .errors import (
    CLIError, APIRequestError, APIAuthError, APIRetriableError,
    AllWatcherStoppedError, InvalidAPIEndpointAddress)


__all__ = [
    "__version__", "JUJU1", "JUJU2",
    "get_cli_class", "prepare_for_bootstrap",
    # errors
    "CLIError", "APIRequestError", "APIAuthError", "APIRetriableError",
    "AllWatcherStoppedError", "InvalidAPIEndpointAddress",
    ]


__version__ = "0.9.0a2"


JUJU1 = "juju-1"
JUJU2 = "juju-2"


def get_cli_class(release=JUJU1):
    """Return the juju CLI wrapper for the given release."""
    from . import cli
    if release == JUJU1:
        return cli.Juju1CLI
    elif release == JUJU2:
        return cli.Juju2CLI
    else:
        raise ValueError("unsupported release {!r}".format(release))


def prepare_for_bootstrap(spec, version, cfgdir):
    """Return the bootstrap config filename after creating configs.

    Note that not all Juju versions have a bootstrap config.  In that
    case None will be returned.

    @param spec: The txjuju.cli.BootstrapSpec for which to prepare.
    @param version: The Juju version to prepare for.
    @param cfgdir: The Juju config directory to use.
    """
    # For now we don't bother with config files for 2.x.
    if version.startswith("2."):
        return None
    cfg = spec.config()
    filenames = cfg.write(cfgdir, version)
    return filenames.get(spec.name) if filenames else None
