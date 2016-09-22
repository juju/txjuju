# Copyright 2016 Canonical Limited.  All rights reserved.

__version__ = "0.9.0a1"


JUJU1 = "juju"
JUJU2 = "juju-2.0"


def get_cli_class(release=JUJU1):
    """Return the juju CLI wrapper for the given release."""
    from . import cli
    if release == JUJU1:
        return cli.Juju1CLI
    elif release == JUJU2:
        return cli.Juju2CLI
    else:
        raise ValueError("unsupported release {!r}".format(release))
