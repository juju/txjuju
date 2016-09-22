# Copyright 2016 Canonical Limited.  All rights reserved.

__version__ = "0.9.0a1"


JUJU1 = "juju"
JUJU2 = "juju-2.0"


def get_process_class(release=JUJU1):
    """Return the juju CLI wrapper for the given release."""
    from . import process
    if release == JUJU1:
        return process.Juju1Process
    elif release == JUJU2:
        return process.Juju2Process
    else:
        raise ValueError("unsupported release {!r}".format(release))
