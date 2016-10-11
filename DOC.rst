*********
txjuju Documentation
*********

Package Content
=========

Essential Modules:

* `txjuju.api <txjuju/api.py>`_    - the Juju API client
* `txjuju.cli <txjuju/cli.py>`_    - the Juju CLI wrapper
* `txjuju.config <txjuju/config.py>`_ - abstraction of Juju's local config

Accessory Modules:

* `txjuju.api_data <txjuju/api_data.py>`_  - API input and output data types
* `txjuju.errors <txjuju/errors.py>`_    - txjuju-specific error classes
* `txjuju.protocol <txjuju/protocol.py>`_  - the twisted protocol used by the API client
* `txjuju.testing.* <txjuju/testing>`_ - test doubles and other testing-related helpers

Constants
---------

In `txjuju <txjuju/__init__.py>`_:

* ``txjuju.__version__``
* ``txjuju.JUJU1`` - represents the Juju 1.x releases
* ``txjuju.JUJU2`` - represents the Juju 2.x releases

Errors
---------

Aliased in `txjuju <txjuju/__init__.py>`_ from `txjuju.errors <txjuju/errors.py>`_:

* ``txjuju.CLIError``
* ``txjuju.APIRequestError``

  * ``txjuju.APIAuthError``
  * ``txjuju.APIRetriableError``

    * ``txjuju.AllWatcherStoppedError``

* ``txjuju.InvalidAPIEndpointAddress``

Config
---------

In `txjuju.config <txjuju/config.py>`_:

* ``Config(*controllers)``

  * ``write(cfgdir, version, clobber=False)``
    -> ``[bootstrap config filenames]``

* ``ControllerConfig(name, cloud, bootstrap=None)``

  * (classmethod) ``from_info(name, type, cloud_name=None,
    default_series=None, admin_secret=None)``

* ``CloudConfig(name, type=None, endpoint=None, auth_types=None,
  credentials=None)``
* ``BootstrapConfig(default_series=None, admin_secret=None)``

Helpers
---------

In `txjuju <txjuju/__init__.py>`_:

* ``txjuju.get_cli_class(release=JUJU1)`` -> `JujuXCLI <txjuju/cli.py>`_
* ``txjuju.prepare_for_bootstrap(spec, version, cfgdir)``
  -> bootstrap config filename

In `txjuju.cli <txjuju/cli.py>`_:

* ``txjuju.cli.get_executable(filename, version_cli, cfgdir, envvars=None)``
  -> `txjuju._utils.Executable <txjuju/_utils.py>`_


API Client
=========

Example Usage
---------

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

API Data Classes
---------

The API client methods produce these.  They align closely with `Juju's
API data types <https://godoc.org/github.com/juju/juju/apiserver/params>`_.

In `txjuju.api_data <txjuju/api_data.py>`_:

* ``APIInfo(endpoints, uuid)``
* ``ModelInfo(name, providerType, defaultSeries, uuid, controllerUUID=None,
  cloud=None, cloudRegion=None, cloudCredential=None)``
* ``CloudInfo(cloudtype, authTypes, endpoint, storageEndpoint, regions)``
* ``MachineInfo(id, instanceId=u"", status=u"pending", statusInfo=u"",
  jobs=None, address=None, hasVote=None, wantsVote=None)``

  * (property) ``is_state_server``

* ``ApplicationInfo(name, exposed=False, charmURL=None, life=None,
  constraints=None, config=None)``
* ``UnitInfo(name, applicationName, series=None, charmURL=None,
  publicAddress=None, privateAddress=None, machineId=u"", ports=(),
  status=None, statusInfo=u"")``
* ``ActionInfo(id, name, receiver, status, message="", results=None)``
* ``WatcherDelta(kind, verb, info)``
* ``ApplicationConfig(application, charm, constraints=None, config=None)``

  * ``has_options(names)``
  * ``get_value(name)``

* ``AnnotationInfo(tag, pairs)``
* ``RunResult(stdout, stderr, code, error)``

Client-related Classes
---------

All of the following methods return twisted deferreds that call back
with values of the indicated type.

In `txjuju.api <txjuju/api.py>`_:

* ``Endpoint(reactor, addr, clientClass, caCert=None, uuid=None)``

  * ``connect()`` -> ``JujuXAPIClient``

* ``Juju2APIClient(protocol)``

  * ``close()``
  * ``login(username, password)`` -> ``APIInfo``
  * ``modelInfo(model_uuid)`` -> ``ModelInfo``
  * ``cloud(cloudname)`` -> ``CloudInfo``
  * ``watchAll()`` -> watcher ID
  * ``allWatcherNext(allWatcherId)`` -> ``[WatcherDelta]``
  * ``destroyMachines(juju_machine_ids)``
  * ``setAnnotations(entityType, entityId, pairs)``
  * ``serviceGet(serviceName)`` -> ``ApplicationConfig``
  * ``serviceSet(serviceName, options)``
  * ``addRelation(endpointA, endpointB)``
  * ``applicationDestroy(applicationName)``
  * ``serviceDeploy(name, charmURL, scope=None, directive=None, config=None)``
  * ``addCharm(charmURL)``
  * ``addUnit(serviceName, scope, directive)`` -> raw response
  * ``addMachine(scope=None, directive=None, parentId=None,
    ubuntu_series=None)`` -> raw response
  * ``run(commands, units, timeout=<300s>)`` -> raw response
  * ``runOnAllMachines(commands, timeout=<300s>)`` -> raw response
  * ``enqueueAction(action, unit, parameters=None)`` -> raw response

* ``Juju1APIClient(protocol)``

  * ``close()``
  * ``login(username, password)`` -> ``APIInfo``
  * ``modelInfo(model_uuid)`` -> ``ModelInfo``
  * ``cloud(cloudname)`` -> ``CloudInfo``
  * ``watchAll()`` -> watcher ID
  * ``allWatcherNext(allWatcherId)`` -> ``[WatcherDelta]``
  * ``destroyMachines(juju_machine_ids)``
  * ``setAnnotations(entityType, entityId, pairs)``
  * ``serviceGet(serviceName)`` -> ``ApplicationConfig``
  * ``serviceSet(serviceName, options)``
  * ``addRelation(endpointA, endpointB)``
  * ``applicationDestroy(applicationName)``
  * ``serviceDeploy(name, charmURL, scope=None, directive=None, config=None)``
  * ``addCharm(charmURL)``
  * ``addUnit(serviceName, scope, directive)`` -> raw response
  * ``addMachine(scope=None, directive=None, parentId=None,
    ubuntu_series=None)`` -> raw response
  * ``run(commands, units, timeout=<300s>)`` -> raw response
  * ``runOnAllMachines(commands, timeout=<300s>)`` -> raw response
  * ``enqueueAction(action, unit, parameters=None)`` -> raw response


CLI Wrapper
=========

Example Usage
---------

.. code:: python

   import pprint
   from twisted.internet import reactor
   from twisted.internet.defer import inlineCallbacks, returnValue
   from txjuju import get_cli_class, JUJU1

   cls = get_cli_class(JUJU1)
   cli = cls("~/.juju")

   @inlineCallbacks
   def bootstrap(name):
       yield cli.boostrap(name, "0")
       raw = yield cli.api_info(name)
       returnValue(raw)

   deferred = bootstrap("my-env")
   deferred.addCallback(lambda v: pprint.pprint(v))

   reactor.run()

Wrapper-related Classes
---------

In `txjuju.cli <txjuju/cli.py>`_:

* ``BootstrapSpec(name, type, default_series=None, admin_secret=None)``
* ``APIInfo(endpoints, user, password, model_uuid=None)``

  * (property) ``address``

* ``CLI(executable, version_cli)``

  * (classmethod) ``from_version(filename, version, cfgdir, envvars=None)``
  * ``bootstrap(spec, to=None, cfgfile=None, verbose=False, gui=False,
    autoupgrade=False)``
  * ``api_info(controller_name=None)`` -> ``APIInfo``
  * ``destroy_controller(name=None, force=False)``

* ``Juju1CLI(juju_home)``

  * ``bootstrap(envname, bootstrap_machine)`` -> raw output (deferred)
  * ``api_info(envname)`` -> raw output (deferred)
  * ``destroy_environment(envname, force=False)`` -> raw output (deferred)
  * ``fetch_file(envname, remote_path, local_dir, machine="0")``
    -> (deferred)
  * ``get_juju_status(envname, output_file_path`` -> (deferred)
  * ``get_all_logs(envname, destdir, filename)`` -> (deferred)

* ``Juju2CLI(juju_data)``

  * ``bootstrap(controllername, bootstrap_machine)`` -> raw output (deferred)
  * ``api_info(controllername)`` -> raw output (deferred)
  * ``destroy_environment(controllername, force=False)``
    -> raw output (deferred)
  * ``fetch_file(modelname, remote_path, local_dir, machine="0")``
    -> (deferred)
  * ``get_juju_status(modelname, output_file_path`` -> (deferred)
  * ``get_all_logs(modelname, destdir, filename)`` -> (deferred)


