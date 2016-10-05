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
