# Copyright 2016 Canonical Limited.  All rights reserved.

"""Twisted client for the Juju Websocket API.

Example::

    endpoint = Endpoint(reactor, "ec2-1-2-3-4.compute-1.amazonaws.com")
    deferred = endpoint.connect()

    @inlineCallbacks
    def connected(client):
        yield client.login("user-admin", "54830489236383334d1d9fd84adae72c")
        yield client.setAnnotations("unit", "1", {"foo": "bar"})

    deferred.addCallback(connected)

"""
from datetime import timedelta

import yaml
from twisted.internet.ssl import ClientContextFactory

from ._twisted.websocketsclient import WebSocketsEndpoint
from .protocol import APIClientFactory
from .api_data import (
    ModelInfo, CloudInfo, UnitInfo, ApplicationInfo, WatcherDelta,
    ApplicationConfig, AnnotationInfo, MachineInfo, ActionInfo, RunResult,
    APIInfo)
from .errors import (
    APIRequestError, InvalidAPIEndpointAddress, AllWatcherStoppedError)


MACHINE_SCOPE = "#"  # For directives targeting machine or container ids


class Endpoint(object):
    """A Juju API endpoint."""

    defaultPort = 17070
    factoryClass = APIClientFactory  # For testing

    def __init__(self, reactor, addr, clientClass, caCert=None,
                 uuid=None):
        """
        @param reactor: The Twisted reactor to use to connect to the endpoint.
        @type reactor: C{twisted.internet.interfaces.IReactor}

        @param addr: The addr name of the state server to connect to, in the
            form 'host:port'. If the ':port' part is omitted the default port
            will be used.
        @type addr: C{str}

        @param clientClass: The APIClient implementation this endpoint uses.
        @type clientClass: Juju1APIClient or Juju2APIClient

        @param caCert: The CA certificate that will be used to validate the
           state server's certificate, in PEM format.
        @type caCert: C{str}

        @param uuid: Model uuid required for juju 2 endpoint construction
        @type uuid: str
        """
        self._reactor = reactor
        self.addr = addr
        self.uuid = uuid
        self._caCert = caCert
        self.clientClass = clientClass

    def connect(self):
        """Connect to the API state server, with a timeout of 20s.

        @return: A deferred that will callback with a connected APIClient
            if we could connect, or errback with the relevant error.
        """
        uri = self._get_uri(self.addr)
        factory = self.factoryClass()
        contextFactory = ClientContextFactory()  # TODO: verify certificate
        endpoint = WebSocketsEndpoint(
            self._reactor, uri, sslContextFactory=contextFactory, timeout=20)
        deferred = endpoint.connect(factory)
        return deferred.addCallback(
            lambda protocol: self.clientClass(protocol))

    def _get_uri(self, addr):
        """Return the API URI for the address.

        Raise an InvalidAPIEndpointAddress exception if the specified
        address is not valid.
        """
        parts = addr.split(":")
        host = parts[0]
        if "/" in host:
            raise InvalidAPIEndpointAddress(addr)

        if len(parts) == 1:
            port = self.defaultPort
        elif len(parts) == 2:
            port = parts[1]
        else:
            raise InvalidAPIEndpointAddress(addr)

        try:
            port = int(port)
        except ValueError:
            raise InvalidAPIEndpointAddress(addr)
        uri = "wss://%s:%d/" % (host, port)
        if self.clientClass is Juju1APIClient:
            return uri
        if self.uuid:
            uri += "model/" + self.uuid + "/api"
        return uri


class Juju2APIClient(object):
    """Client for the Juju 2.0 API.

    Each method of this class will perform the relevant Juju 2.0 API request
    and return a C{Deferred} firing with the response of the request.
    """

    # Used for parsing api responses. Keys differ across juju major versions.
    _api_application_facade = "Application"
    _api_info_entity_prefix = "model-"
    _api_container_type = "lxd"
    _api_run_facade = "Action"
    _API_FACADE_VERSIONS = {
        "Admin": {
            "Login": 3},
        "Action": {
            "Enqueue": 2,
            "RunOnAllMachines": 2,
            "Run": 2},
        "AllWatcher": {
            "Next": 1},
        "Annotations": {
            "Set": 2},
        "Application": {
            "AddRelation": 1,
            "AddUnits": 1,
            "Deploy": 1,
            "Destroy": 1,
            "Get": 1,
            "Set": 1},
        "Client": {
            "AddMachines": 1,
            "AddCharm": 1,
            "DestroyMachines": 1,
            "WatchAll": 1},
        "Cloud": {
            "Cloud": 1},
        "ModelManager": {
            "ModelInfo": 2},
    }
    _LOOKUP_PARAMETERS = {
        "application-name": "application",
    }
    # Skip parameter conversion for any values below these keys
    _SKIP_CONVERSION = ["Options", "Pairs", "parameters", "Config"]

    def __init__(self, protocol):
        """
        @param protocol: A connected JujuProtocol instance.
        @type protocol: JujuProtocol
        """
        self._protocol = protocol

    def login(self, username, password):
        """Authenticate using the given credentials.

        @param username: Identifies the user to authenticate as.
        @param password: Password for the administrator or connecting entity.
        @return: A deferred which will callback with an APIInfo.
        """
        tag = username
        if not tag.startswith("user-"):
            tag = "user-" + tag
        params = {"auth-tag": tag, "credentials": password}
        deferred = self._sendRequest("Admin", "Login", params=params)
        return deferred.addCallback(self._parseApiInfo)

    def modelInfo(self, model_uuid):
        """Return information about the model.

        @param model_uuid: the UUID of the model to look up.
        @return: A deferred which will callback with a ModelInfo.
        """
        params = {"entities": [{"tag": "model-" + model_uuid}]}
        deferred = self._sendRequest("ModelManager", "ModelInfo",
                                     params=params)
        return deferred.addCallback(self._parseModelInfo)

    def cloud(self, cloudtag):
        """Return information about the model's cloud.

        @return: A deferred which will callback with a CloudInfo.
        """
        params = {"entities": [{"tag": cloudtag}]}
        deferred = self._sendRequest("Cloud", "Cloud", params=params)
        return deferred.addCallback(self._parseCloudResponse)

    def watchAll(self):
        """Start watching for changes across the whole model.

        @return: A deferred which will callback with an "allWatcher"
            C{str} identifier, that can be passed to L{allWatcherNext} to get
            a batch of model changes.
        """
        deferred = self._sendRequest("Client", "WatchAll")
        return deferred.addCallback(self._parseWatchAll)

    def allWatcherNext(self, allWatcherId):
        """Get the next batch of change notifications.

        The server won't really "execute" this request, but rather take note
        that we're interested in the next batch of changes and send them to
        us when they are available. The returned C{Deferred} will callback
        at that point.

        @param allWatcherId: The token returned by a former C{watchAll} call.
        @type allWatcherId: C{str}

        @return: A deferred that will call back with a C{list} of
            L{WatcherDelta} instances describing what has changed.
        """
        deferred = self._sendRequest(
            "AllWatcher", "Next", entityId=allWatcherId)
        deferred.addCallback(self._parseAllWatcherNext)
        deferred.addErrback(self._parseAllWatcherNextError)
        return deferred

    def destroyMachines(self, juju_machine_ids):
        """Release a list of juju machines from the model.

        This also releases any resident containers and units created on those
        machines.
        @param juju_machine_ids: List of integers representing juju machine
            ids to release.
        """
        params = {"force": True,
                  "machine-names": [
                      "%s" % machine_id for machine_id in juju_machine_ids]}
        return self._sendRequest("Client", "DestroyMachines", params=params)

    def setAnnotations(self, entityType, entityId, pairs):
        """Add the given annotations to the given entity.

        @param entityType: The type of the entity to tag (e.g. "unit").
        @type entityType: str

        @param entityId: The id of the entity to tag (e.g. "1").
        @type entityId: str

        @param pairs: A dict of str to str mapping the tags to add
            to their values.
        @type pairs: dict
        """
        params = {"annotations": [
            {"entity": "{}-{}".format(entityType, entityId),
             "annotations": pairs}]}
        deferred = self._sendRequest(
            "Annotations", "Set", params=params)
        return deferred.addCallback(lambda _: None)  # No data in the response

    def serviceGet(self, serviceName):
        """Get the configuration of the service with the given name."""
        params = {"application": serviceName}
        deferred = self._sendRequest(
            self._api_application_facade, "Get", params=params)
        return deferred.addCallback(self._parseServiceGet)

    def serviceSet(self, serviceName, options):
        """Set the configuration of the service with the given name."""
        params = {"application": serviceName,
                  "options": options}
        deferred = self._sendRequest(
            self._api_application_facade, "Set", params=params)
        return deferred.addCallback(lambda result: None)

    def addRelation(self, endpointA, endpointB):
        """
        Add a relation between two Juju service endpoints.

        @param endpointA: A relation endpoint, such as "mysql:db"
        @param endpointB: Another relation endpoint, such as "wordpress:db"
        """
        params = {"Endpoints": [endpointA, endpointB]}
        deferred = self._sendRequest(
            self._api_application_facade, "AddRelation", params=params)
        return deferred.addCallback(lambda _: None)

    def _sendRequest(self, entityType, request, entityId=None, params=None):
        """Return a deferred sendRequest with the proper facade_version."""
        converted_params = self._convertParamKeys(params)
        facade_version = None
        if entityType in self._API_FACADE_VERSIONS:
            facade_version = (
                self._API_FACADE_VERSIONS[entityType].get(request))
        return self._protocol.sendRequest(
            entityType, request, entityId=entityId, params=converted_params,
            facade_version=facade_version)

    def _getCamelCaseParam(self, param):
        """Return the unaltered param value for juju-2.0.

        Juju-2.0 uses almost exclusively lowercase, hyphenated parameters.
        """
        return param

    def _getParam(self, param):
        """Lookup the appropriate parameter to use in API calls."""
        try:
            return self._LOOKUP_PARAMETERS[param]
        except KeyError:
            return self._getCamelCaseParam(param)

    def _convertParamKeys(self, params):
        """Convert parameter keys for compatibility with the API version."""
        if not params:
            return {}
        if isinstance(params, str) or isinstance(params, unicode):
            return params
        converted_params = {}
        for key, value in params.items():
            if isinstance(value, list):
                value = [self._convertParamKeys(item) for item in value]
            elif (isinstance(value, dict) and
                  key not in self._SKIP_CONVERSION):
                value = self._convertParamKeys(value)
            converted_params[self._getParam(key)] = value
        return converted_params

    def _getPlacementParam(self, scope, directive):
        """Return placement parameter for Juju 2.0."""
        if not any([scope, directive]):
            return {}
        if scope is None:
            scope = MACHINE_SCOPE
        return {"placement": [{"scope": scope,
                               "directive": directive}]}

    def _getServiceDeployParams(self, serviceName, charmURL, scope=None,
                                directive=None, config=None):
        """Return a dictionary of service deploy request parameters.

        @param serviceName: The name of the service.
        @param charmURL: The URL of the charm (e.g. cs:precise/ubuntu-2).
        @param config: an optional C{dict} containing charm configuration.
        @param scope: When using machine placement, the scope to use (for
            example the model UUID or MACHINE_SCOPE).
        @param directive: When using placement, the directive to use. One of:
                - a maas hostname
                - an existing machine/container id, eg. "1" or "1/lxc/2"
        """
        if config is None:
            config = {}
        params = {"application-name": serviceName,
                  "charm-url": charmURL,
                  # Use the YAML config since it allows setting empty values
                  # for keys.
                  "config-yaml": yaml.dump({serviceName: config}),
                  "num-units": 1}
        if any([scope, directive]):
            params.update(self._getPlacementParam(scope, directive))
        else:
            # Subordinate charms have a null placement and should have
            # 0 NumUnits
            params["num-units"] = 0
        return params

    def applicationDestroy(self, applicationName):
        """Destroy a juju application.

        @param applicationName: The name of the application.
        """
        params = {"application": applicationName}
        deferred = self._sendRequest(
            self._api_application_facade, "Destroy", params=params)
        return deferred.addCallback(lambda _: None)  # No data in the response

    def serviceDeploy(self, serviceName, charmURL, scope=None, directive=None,
                      config=None):
        """Deploy a Juju service

        @param serviceName: The name of the service.
        @param charmURL: The URL of the charm (e.g. cs:precise/ubuntu-2).
        @param config: an optional C{dict} containing charm configuration.
        @param scope: When using machine placement, the scope to use (for
            example the model UUID or MACHINE_SCOPE).
        @param directive: When using placement, the directive to use. One of:
                - a maas hostname
                - an existing machine/container id, eg. "1" or "1/lxc/2"
        """
        application_params = self._getServiceDeployParams(
            serviceName, charmURL, scope, directive, config)
        application_params["channel"] = "stable"
        # In Juju 2.0, multiple applications could be deployed in one request
        # by specifying a parameters dict as an item in the Applications list.
        deferred = self._sendRequest(
            self._api_application_facade, "Deploy",
            params={"applications": [application_params]})
        return deferred.addCallback(self._parseErrorResults)

    def addCharm(self, charmURL):
        """Add a charm to the juju model so that it may be deployed."""
        params = {"url": charmURL}
        deferred = self._sendRequest("Client", "AddCharm", params=params)
        return deferred.addCallback(self._parseAddCharm)

    def addUnit(self, serviceName, scope, directive):
        """Add a unit to a Juju service.

        @param serviceName: The name of the service.
        @param scope: When using machine placement, the scope to use (for
            example the model UUID or MACHINE_SCOPE).
        @param directive: When using placement, the directive to use. One of:
                - a maas hostname
                - an existing machine/container id, eg. "1" or "1/lxc/2"
        """
        params = {"application": serviceName,
                  "num-units": 1}
        params.update(self._getPlacementParam(scope, directive))
        deferred = self._sendRequest(
            self._api_application_facade, "AddUnits", params=params)
        return deferred.addCallback(self._parseAddServiceUnits)

    def addMachine(self, scope=None, directive=None, parentId=None,
                   ubuntu_series=None):
        """Add a machine or container to the model.

        @param scope: When using machine placement, the scope to use (for
            example the model UUID).
        @param directive: When using placement, the directive to use (for
            example the hostname of the machine, for a MAAS provider).
        @param parentId: The id of the Juju machine on which to create a
            container.
        @param ubuntu_series: The series to deploy (if desired).
        @return: A deferred firing with the Juju machine ID of newly created
            machine or container.
        """
        machine = {"jobs": ["JobHostUnits"]}

        if scope and directive:
            machine["placement"] = {
                "scope": scope,
                "directive": directive}
        if parentId:
            machine["parent-id"] = parentId
            machine["container-type"] = self._api_container_type
        if ubuntu_series:
            machine["series"] = ubuntu_series
        params = {"params": [machine]}
        deferred = self._sendRequest("Client", "AddMachines", params=params)
        return deferred.addCallback(self._parseAddMachines)

    def run(self, commands, units, timeout=timedelta(seconds=300)):
        """Run a command on selected machines.

        @param commands: A string with the commands to run.
        @param units: A list of units to run the command on.
        @param timeout: A timedelta object representing timeout,
            defaults to 5 minutes.

        @return: A deferred firing with a dictionary mapping unit
            names to a RunResult.

        """
        # Juju API barfs on floats, let's make it an integer.
        timeout_nanoseconds = int(timeout.total_seconds() * 10 ** 9)
        params = {"commands": commands,
                  "timeout": timeout_nanoseconds,
                  "units": units}
        deferred = self._sendRequest(
            self._api_run_facade, "Run", params=params)
        return deferred.addCallback(self._parseRun)

    def runOnAllMachines(self, commands, timeout=timedelta(seconds=300)):
        """Run a command on all machines.

        @param commands: A string with the commands to run.
        @param timeout: A timedelta object representing timeout,
            defaults to 5 minutes.

        @return: A deferred firing with a dictionary mapping unit
            names to a RunResult.

        """
        # Juju API barfs on floats, let's make it an integer.
        timeout_nanoseconds = int(timeout.total_seconds() * 10 ** 9)
        params = {"commands": commands,
                  "timeout": timeout_nanoseconds}
        deferred = self._sendRequest(
            self._api_run_facade, "RunOnAllMachines", params=params)
        return deferred.addCallback(self._parseRunOnAllMachines)

    def enqueueAction(self, action, unit, parameters=None):
        """Enqueue an action on a unit."""
        receiver = "unit-%s" % unit.replace("/", "-")
        params = {
            "actions": [
                {"name": action,
                 "receiver": receiver,
                 "parameters": parameters or {}}]}
        deferred = self._sendRequest("Action", "Enqueue", params=params)
        deferred.addCallback(self._parseEnqueueActions)
        return deferred.addCallback(self._parseSingleAction)

    def close(self):
        """Close the connection with the API server."""
        self._protocol.transport.loseConnection()
        return self._protocol.disconnected

    def _parseAddCharm(self, response):
        """Parse the AddCharm API response for errors."""
        error = response.get("Error")  # XXX Watch for param renames
        if error:
            raise APIRequestError(error, code="")  # No error code is defined

    def _parseApiInfo(self, response):
        """Parse controller/model API endpoints information."""
        endpoints = []
        tag = response.get(self._getParam("model-tag"))
        uuid = None
        if tag:
            uuid = tag.replace(self._api_info_entity_prefix, "")
        for server in response.get(self._getParam("servers"), []):
            for endpoint in server:
                if self._isUsableEndpoint(endpoint):
                    endpoints.append(
                        u"%s:%d" % (endpoint[self._getParam("value")],
                                    endpoint[self._getParam("port")]))

        return APIInfo(endpoints, uuid)

    def _isUsableEndpoint(self, endpoint):
        """Whether the given address is a usable state server endpoint.

        We require the address to be a non-local IPv4 address. Alternatively,
        we consider the endpoint usable if it's a fake-juju one.
        """
        # XXX workaround until lp:1597372 gives us consistency in juju2beta10
        scope = endpoint.get("Scope") or endpoint.get("scope")
        type_ = endpoint.get("Type") or endpoint.get("type")

        network = endpoint.get(self._getParam("space-name"))
        if scope != "local-machine" and type_ == "ipv4":
            return True
        # This is not a non-local IPv4 address, let's check if it's a
        # fake-juju one instead.
        return network == "dummy-provider-network" and type_ == "hostname"

    def _parseModelInfo(self, response):
        """Parse the response of a modelInfo request."""
        try:
            results = response["results"]
        except KeyError:
            raise APIRequestError("malformed response {}".format(response), "")
        apiresult = _extract_single_result(results)
        _handle_api_error(apiresult)
        result = apiresult["result"]
        return self._parseModelInfoResult(result)

    def _parseModelInfoResult(self, result):
        """Return the ModelInfo from the provided raw result."""
        try:
            return ModelInfo(
                result[self._getParam("name")],
                result[self._getParam("provider-type")],
                result[self._getParam("default-series")],
                result[self._getParam("uuid")],
                result.get(self._getParam("controller-uuid")),
                result.get(self._getParam("cloud-tag")),
                result.get(self._getParam("cloud-region")),
                result.get(self._getParam("cloud-credential-tag")),
                )
        except KeyError:
            raise APIRequestError("malformed result {}".format(result), "")

    def _parseCloudResponse(self, response):
        """Parse the response of a Cloud.Cloud request.

        See:
          https://godoc.org/github.com/juju/juju/apiserver/params#CloudResults
        """
        result = response["results"][0]
        err = result.get("error")
        if err is not None:
            raise APIRequestError(
                err[self._getParam("message")],
                err[self._getParam("code")])
        cloud = result["cloud"]
        return CloudInfo(
            cloud[self._getParam("type")],
            cloud.get(self._getParam("auth-types"), []),
            cloud.get(self._getParam("endpoint")),
            cloud.get(self._getParam("storage-endpoint")),
            cloud.get(self._getParam("regions"), []),
            )

    def _getDeltaJujuStatus(self, delta):
        """Return a tuple of juju status and status-info for juju2 deltas."""
        jujuStatus = delta.get(self._getParam("agent-status"), {})
        return (jujuStatus.get(self._getParam("current"), u""),
                jujuStatus.get(self._getParam("message"), u""))

    def _parseWatchAll(self, response):
        """Parse the response of a L{watchAll} request."""
        return response[self._getParam("watcher-id")]

    def _parseAllWatcherNext(self, response):
        """Parse the response of an AllWatcherNext request.

        See github.com/juju/juju/state/multiwatcher/multiwatcher.go.
        """
        deltas = []
        for kind, verb, data in response[self._getParam("deltas")]:
            info = self._parseAllWatcherNextDelta(kind, data)
            if info is None:
                continue
            delta = WatcherDelta(kind, verb, info)
            deltas.append(delta)
        return deltas

    def _parseAllWatcherNextDelta(self, kind, data):
        """Parse the data based on the provided entity kind.

        "data" is the raw delta info from a single delta in the list
        of deltas in a response to an AllWatcherNext Juju API request.
        """
        if kind == "unit":
            # TODO: None of these should be optional (no data.get).
            status, statusInfo = self._getDeltaJujuStatus(data)
            info = UnitInfo(
                data[self._getParam("name")],
                data[self._getParam("application")],
                series=data.get(self._getParam("series")),
                charmURL=data.get(self._getParam("charm-url")),
                publicAddress=data.get(self._getParam("public-address")),
                privateAddress=data.get(self._getParam("private-address")),
                machineId=data.get(self._getParam("machine-id")),
                ports=data.get(self._getParam("ports")),
                status=status,
                statusInfo=statusInfo,
                )
        elif kind == "application":
            # TODO: None of these should be optional (no data.get).
            info = ApplicationInfo(
                data[self._getParam("name")],
                exposed=data.get(self._getParam("exposed")),
                charmURL=data.get(self._getParam("charm-url")),
                life=data.get(self._getParam("life")),
                constraints=data.get(self._getParam("constraints")),
                config=data.get(self._getParam("config")),
                )
        elif kind == "annotation":
            info = AnnotationInfo(
                data[self._getParam("tag")],
                data[self._getParam("annotations")],
                )
        elif kind == "machine":
            # TODO: None of these should be optional (no data.get).
            status, statusInfo = self._getDeltaJujuStatus(data)
            # beta11 addresses will be None instead of [] when pending
            address = self._parseAddresses(
                data.get(self._getParam("addresses")) or [])
            info = MachineInfo(
                data[self._getParam("id")],
                instanceId=data[self._getParam("instance-id")],
                status=status,
                statusInfo=statusInfo,
                jobs=data.get(self._getParam("jobs")),
                address=address,
                hasVote=data.get(self._getParam("has-vote")),
                wantsVote=data.get(self._getParam("wants-vote")),
                )
        elif kind == "action":
            results = data.get(self._getParam("results"))
            info = ActionInfo(
                data[self._getParam("id")],
                data[self._getParam("name")],
                data[self._getParam("receiver")],
                data[self._getParam("status")],
                message=data[self._getParam("message")],
                results=results,
                )
        # TODO implement the 'relation' kind
        else:
            # Unknown kinds are silently dropped, for forward compatibility
            return None
        return info

    def _parseAddresses(self, addresses):
        """Return the first non-local IPv4 address, if any."""
        for address in addresses:
            if self._isUsableEndpoint(address):
                return address[self._getParam("value")]

    def _parseAllWatcherNextError(self, failure):
        """
        Raise C{AllWatcherStoppedError} if the watcher was stopped,
        otherwise allow other exceptions to pass through.
        """
        failure.trap(APIRequestError)
        # Bug:1396680 From casual reading of Juju code, this error
        # is what happens when Juju upgrades the tools on the state
        # server.
        #
        # The exact error message is defined in juju/state/multiwatcher.go
        # (see ErrWatcher), however it's not clear what the API-level
        # error code for this failure mode is, so we resort checking the
        # human-oriented message.
        if failure.value.error == "watcher was stopped":
            raise AllWatcherStoppedError(
                failure.value.error, failure.value.code)
        else:
            failure.raiseException()

    def _parseServiceGet(self, response):
        """Parse the response of a L{serviceGet} request."""
        return ApplicationConfig(
            response[self._getParam("application")],
            response[self._getParam("charm")],
            constraints=response.get(self._getParam("constraints")),
            config=response.get(self._getParam("config")))

    def _parseAddMachines(self, response):
        """Parse the response of a L{addMachines} request."""
        return response[
            self._getParam("machines")][0][self._getParam("machine")]

    def _parseAddServiceUnits(self, response):
        """Parse the response of an AddServiceUnits request."""
        return response[self._getParam("units")][0]

    def _parseRun(self, response):
        """Parse the response of a run request."""
        results = {}
        for result in response[self._getParam("results")]:
            results[result["UnitId"]] = RunResult(
                result["Stdout"].decode("base64"),
                result["Stderr"].decode("base64"),
                result["Code"],
                result["Error"])
        return results

    def _parseRunOnAllMachines(self, response):
        """Parse the response of a runOnAllMachines request."""
        # juju-2.0 uses asynch behavior and returns a list of pending actions
        return self._parseEnqueueActions(response)

    def _parseSingleAction(self, response):
        """Return a singleaction from the response list."""
        return response[0]

    def _parseEnqueueActions(self, response):
        """Parse the response for an enqueueAction request.

        @return: A list of strings containing action ids.
        """
        action_ids = []
        for result in response["results"]:
            error = result.get("error")
            if error is not None:
                raise APIRequestError(
                    error[self._getParam("message")],
                    error[self._getParam("code")])
            action_tag = result["action"]["tag"]
            action_ids.append(action_tag.replace("action-", ""))
        return action_ids

    def _parseErrorResults(self, response):
        """Raise an exception if the response has any errors in it."""
        for result in response["results"]:
            _handle_api_error(result)


class Juju1APIClient(Juju2APIClient):
    """Client for the Juju 1.X API.

    XXX bug #1558600 duplication to be removed with "juju-2.0" feature flag.
    Each method of this class will perform the relevant Juju 1.0 API request
    and return a C{Deferred} firing with the response of the request.
    """

    # Used for parsing api responses. Keys differ across juju major versions.
    _api_application_facade = "Service"
    _api_entity_key = "EntityTag"
    _api_error_code_key = "Code"
    _api_error_message_key = "Message"
    _api_info_entity_prefix = "environment-"
    _api_run_facade = "Client"
    _api_container_type = "lxc"
    _API_FACADE_VERSIONS = {}
    _LOOKUP_PARAMETERS = {
        "agent-status": "JujuStatus",
        "application": "Service",
        "application-name": "ServiceName",
        "charm-url": "CharmURL",
        "config-yaml": "ConfigYAML",
        "model-tag": "EnvironTag",
        "params": "MachineParams",
        "space-name": "NetworkName",
        "watcher-id": "AllWatcherId",
        "uuid": "UUID"}

    def login(self, tag, password):
        """Authenticate using the given credentials.

        @param tag: The name of the entity to authenticate as.
        @type tag: C{str}

        @param password: Password for the administrator or connecting entity.
        @type password: C{str}

        @return: A deferred which will callback with an APIInfo.
        """
        params = {"AuthTag": tag, "Password": password}
        deferred = self._sendRequest("Admin", "Login", params=params)
        return deferred.addCallback(self._parseApiInfo)

    def modelInfo(self, model_uuid):
        """Return information about the model.

        The model_uuid argument is ignored.  It's only needed for
        the 2.0 client.  For 1.X there is no multi-model support.

        @return: A deferred which will callback with a ModelInfo
            instance.
        """
        deferred = self._sendRequest("Client", "EnvironmentInfo")
        return deferred.addCallback(self._parseModelInfo)

    def cloud(self, cloudname):
        """Return information about the model's cloud.

        Note: this shouldn't be called for Juju 1.x.  Consequently, it
        hasn't been implemented and will result in a RuntimeError.

        @return: A deferred which will callback with a CloudInfo.
        """
        raise RuntimeError("not supported under Juju 1.X")

    def serviceDeploy(self, serviceName, charmURL, scope=None,
                      directive=None, config=None):
        """Deploy a Juju service

        @param serviceName: The name of the service.
        @param charmURL: The URL of the charm (e.g. cs:precise/ubuntu-2).
        @param config: an optional C{dict} containing charm configuration.
        @param scope: When using machine placement, the scope to use (for
            example the model UUID or MACHINE_SCOPE).
        @param directive: When using placement, the directive to use. One of:
                - a maas hostname
                - an existing machine/container id, eg. "1" or "1/lxc/2"
        """
        params = self._getServiceDeployParams(
            serviceName, charmURL, scope, directive, config)
        deferred = self._sendRequest("Client", "ServiceDeploy", params=params)
        return deferred.addCallback(lambda _: None)  # No data in the response

    def addUnit(self, serviceName, scope, directive):
        """Add a unit to a Juju service in Juju 1.X.

        @param serviceName: The name of the service.
        @param scope: When using machine placement, the scope to use (for
            example the model UUID or MACHINE_SCOPE).
        @param directive: When using placement, the directive to use. One of:
                - a maas hostname
                - an existing machine/container id, eg. "1" or "1/lxc/2"
        """
        params = {"application-name": serviceName, "num-units": 1}
        params.update(self._getPlacementParam(scope, directive))
        deferred = self._sendRequest(
            "Client", "AddServiceUnits", params=params)
        return deferred.addCallback(self._parseAddServiceUnits)

    def serviceGet(self, serviceName):
        """Get the configuration of the service with the given name."""
        params = {"ServiceName": serviceName}
        deferred = self._sendRequest("Client", "ServiceGet", params=params)
        return deferred.addCallback(self._parseServiceGet)

    def serviceSet(self, serviceName, options):
        """Set the configuration of the service with the given name."""
        params = {"ServiceName": serviceName, "Options": options}
        deferred = self._sendRequest("Client", "ServiceSet", params=params)
        return deferred.addCallback(lambda result: None)

    def setAnnotations(self, entityType, entityId, pairs):
        """Add the given annotations to the given entity.

        @param entityType: The type of the entity to tag (e.g. "unit").
        @type entityType: str

        @param entityId: The id of the entity to tag (e.g. "1").
        @type entityId: str

        @param pairs: A dict of str to str mapping the tags to add
            to their values.
        @type pairs: dict
        """
        params = {"Tag": "{}-{}".format(entityType, entityId), "Pairs": pairs}
        deferred = self._sendRequest(
            "Client", "SetAnnotations", params=params)
        return deferred.addCallback(lambda _: None)  # No data in the response

    def addRelation(self, endpointA, endpointB):
        """
        Add a relation between two Juju 1.X service endpoints.

        @param endpointA: A relation endpoint, such as "mysql:db"
        @param endpointB: Another relation endpoint, such as "wordpress:db"
        """
        params = {"Endpoints": [endpointA, endpointB]}
        deferred = self._sendRequest("Client", "AddRelation", params=params)
        return deferred.addCallback(lambda _: None)

    def _parseModelInfo(self, response):
        """Parse the response of a modelInfo request."""
        return self._parseModelInfoResult(response)

    def _getDeltaJujuStatus(self, delta):
        """Return a tuple of juju status and status-info for juju1 deltas."""
        return delta.get("Status", u""), delta.get("StatusInfo", u"")

    def _getPlacementParam(self, scope=None, directive=None):
        """Return placement parameter for Juju 1.0."""
        return {"ToMachineSpec": directive}

    def _parseAllWatcherNextDelta(self, kind, data):
        if kind == "service":
            kind = "application"
        return (super(Juju1APIClient, self)
                )._parseAllWatcherNextDelta(kind, data)

    def _parseRunOnAllMachines(self, response):
        """Parse the response of a runOnAllMachines request."""
        # juju1 has synch response containing run results of the command
        return {
            result["MachineId"]: RunResult(
                result["Stdout"].decode("base64"),
                result["Stderr"].decode("base64"),
                result["Code"],
                result["Error"])
            for result in response["Results"]}

    def _getCamelCaseParam(self, param):
        """Return CamelCase of a hyphen-delimited param for juju1."""
        if "-" not in param and param[0].isupper():
            # We are already uppercase and not hyphenated
            return param
        return "".join([part.capitalize() for part in param.split("-")])


def _extract_single_result(results):
    """Return the result in the list.

    If results is empty or larger than one then raise an APIRequestError.
    """
    if not results:
        raise APIRequestError("expected 1 result, got none", "")  # no code
    if len(results) > 1:
        msg = "expected 1 result, got {}".format(len(results))
        raise APIRequestError(msg, "")  # no code
    return results[0]


def _handle_api_error(result):
    """Raise an APIRequestError if the result contains an error."""
    error = result.get("error")
    if not error:
        return
    try:
        msg = error["message"] or "error"
        code = error["code"]
    except KeyError:
        raise APIRequestError("malformed result {}".format(result), "")
    raise APIRequestError(msg, code)
