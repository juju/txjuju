*********
txjuju: a twisted-based Juju client
*********

``txjuju`` provides `twisted <https://twistedmatrix.com/>`_-based tools
for interacting with `Juju <http://www.ubuntu.com/cloud/juju>`_.  This
includes both an API client and a CLI wrapper.  The library is limited
to Python 2, but does support both Juju 1.x and 2.x.  Support for
Python 3 is on the radar.

Note that only a portion of Juju's capability is exposed in txjuju.
This is because the code originates in the
`Landscape <https://landscape.canonical.com/>`_ project and did not grow
much beyond the needs of Landscape.  The official `Python bindings for
Juju <https://github.com/juju-solutions/python-libjuju>`_ will usually
offer a better experience.  At some point ``python-libjuju`` may
entirely supercede txjuju.


Contributing
=========

If you'd like to contribute to txjuju, feel free to open an issue or
send us a pull request.  As far as borrowing from txjuju goes, the
code is LGPLv3-licensed.

Packaging
---------

A Python package may be created using ``python2 setup.py sdist``.
For building a debian package see ``BUILD`` and ``build.sh``.

Style
---------

The txjuju code follows PEP 8.  It is a good idea to frequently run
something like `flake8 <https://pypi.python.org/pypi/flake8>`_ when
making changes.  Other txjuju-specific guidelines:

* use double quotes for strings
* test methods should have docstrings

Testing
---------

To run the test suite, run ``make test`` or
``python2 -m unittest txjuju.tests.test_XXX``.
