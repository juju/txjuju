***********************************
txjuju: a twisted-based Juju client
***********************************

``txjuju`` provides `twisted <https://twistedmatrix.com/>`_-based tools
for interacting with `Juju <http://www.ubuntu.com/cloud/juju>`_.  This
includes both an API client and a CLI wrapper.  The library is limited
to Python 2, but does support both Juju 1.x and 2.x.  Support for
Python 3 is on the radar.

Note that only a portion of Juju's capability is exposed in txjuju.
This is because the code originates in the
`Landscape <https://landscape.canonical.com/>`_ project and did not grow
much beyond the needs of Landscape.  The official Python bindings for
Juju (`python-libjuju <https://github.com/juju-solutions/python-libjuju>`_)
will usually offer a better experience.  At some point python-libjuju
may entirely supercede txjuju.


Key Components
==============

Here are the essential classes of txjuju:

* `txjuju.api.Endpoint <txjuju/api.py>`_
* `txjuju.api.Juju2APIClient <txjuju/api.py>`_ and `txjuju.api.Juju1APIClient <txjuju/api.py>`_
* `txjuju.cli.Juju2CLI <txjuju/cli.py>`_ and `txjuju.cli.Juju1CLI <txjuju/cli.py>`_

Additionally, `txjuju.prepare_for_bootstrap() <txjuju/__init__.py>`_ is especially useful.

For more information see `DOC.rst <DOC.rst>`_.


Example Usage
=============

API Client
----------

.. code:: python

   from twisted.internet import reactor
   from twisted.internet.defer import inlineCallbacks
   from txjuju.api import Endpoint

   endpoint = Endpoint(reactor, "ec2-1-2-3-4.compute-1.amazonaws.com")
   deferred = endpoint.connect()

   @inlineCallbacks
   def connected(client):
       yield client.login("user-admin", "54830489236383334d1d9fd84adae72c")
       yield client.setAnnotations("unit", "1", {"foo": "bar"})

   deferred.addCallback(connected)

   reactor.run()

CLI Wrapper
-----------

.. code:: python

   import pprint
   from twisted.internet import reactor
   from twisted.internet.defer import inlineCallbacks, returnValue
   from txjuju import prepare_for_bootstrap
   from txjuju.cli import BootstrapSpec, Juju1CLI

   cfgdir = "/tmp/my-juju"
   spec = BootstrapSpec("my-env", "lxd")
   cli = Juju1CLI(cfgdir)

   @inlineCallbacks
   def bootstrap():
       prepare_for_bootstrap(spec, "1.25.6", cfgdir)
       yield cli.boostrap(spec.name, "0")
       raw = yield cli.api_info(spec.name)
       returnValue(raw)

   deferred = bootstrap()
   deferred.addCallback(lambda v: pprint.pprint(v))

   reactor.run()


Contributing
============

If you'd like to contribute to txjuju, feel free to open an issue or
send us a pull request.  As far as borrowing from txjuju goes, the
code is LGPLv3-licensed.

Packaging
---------

A Python package may be created using ``python2 setup.py sdist``.
For building a debian package see `BUILD <BUILD>`_ and
`build.sh <build.sh>`_.

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
