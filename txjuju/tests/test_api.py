# Copyright 2016 Canonical Limited.  All rights reserved.

from datetime import timedelta

import yaml
from twisted.trial.unittest import TestCase
from twisted.test.proto_helpers import MemoryReactorClock
from txjuju_testing.api import FakeAPIBackend

from txjuju.protocol import APIClientFactory
from txjuju.api import (
    Endpoint, Juju1APIClient, Juju2APIClient, MACHINE_SCOPE)
from txjuju.errors import (
    APIRequestError, InvalidAPIEndpointAddress, AllWatcherStoppedError)


class EndpointTest(TestCase):

    def setUp(self):
        super(EndpointTest, self).setUp()
        self.reactor = MemoryReactorClock()
        self.endpoint = Endpoint(self.reactor, "host", Juju1APIClient)

    def test_connect(self):
        """
        The connect method uses the endpoint information provided in
        the constructor.
        """
        factory = APIClientFactory()
        self.endpoint.factoryClass = lambda: factory
        self.endpoint.connect()
        [(host, port, _, _, _, _)] = self.reactor.sslClients
        self.assertEqual("host", host)
        self.assertEqual(17070, port)

    def test_connect_non_default_port(self):
        """It's possible to specify a different port in the endpoint."""
        self.endpoint = Endpoint(self.reactor, "host:1234", Juju1APIClient)
        factory = APIClientFactory()
        self.endpoint.factoryClass = lambda: factory
        self.endpoint.connect()
        [(host, port, _, _, _, _)] = self.reactor.sslClients
        self.assertEqual("host", host)
        self.assertEqual(1234, port)

    def test_wb_get_uri(self):
        """The _get_uri method returns the endpoint URI."""
        self.assertEqual(
            "wss://1.2.3.4:17070/", self.endpoint._get_uri("1.2.3.4"))
        self.assertEqual(
            "wss://1.2.3.4:5678/", self.endpoint._get_uri("1.2.3.4:5678"))
        self.assertEqual(
            "wss://juju-host:17070/", self.endpoint._get_uri("juju-host"))
        self.assertEqual(
            "wss://juju-host:5678/", self.endpoint._get_uri("juju-host:5678"))

    def test_wb_get_uri_juju2(self):
        """The _get_uri method returns the Juju 2.0 model endpoint URI."""
        endpoint = Endpoint(
            self.reactor, "host", clientClass=Juju2APIClient, uuid="uuid-123")
        self.assertEqual(
            "wss://1.2.3.4:17070/model/uuid-123/api",
            endpoint._get_uri("1.2.3.4"))
        self.assertEqual(
            "wss://1.2.3.4:5678/model/uuid-123/api",
            endpoint._get_uri("1.2.3.4:5678"))
        self.assertEqual(
            "wss://juju-host:17070/model/uuid-123/api",
            endpoint._get_uri("juju-host"))
        self.assertEqual(
            "wss://juju-host:5678/model/uuid-123/api",
            endpoint._get_uri("juju-host:5678"))

    def test_wb_get_uri_invalid(self):
        """
        The _get_uri method raises an exception if the the address is
        invalid.
        """
        with self.assertRaises(InvalidAPIEndpointAddress):
            self.endpoint._get_uri("http://www.example.com/")
        with self.assertRaises(InvalidAPIEndpointAddress):
            self.endpoint._get_uri("1.2.3.4:badport")
        with self.assertRaises(InvalidAPIEndpointAddress):
            self.endpoint._get_uri("www.example.com/foo")
        with self.assertRaises(InvalidAPIEndpointAddress):
            self.endpoint._get_uri("/www.example.com")


class Juju1APIClientTest(TestCase):

    def setUp(self):
        super(Juju1APIClientTest, self).setUp()
        self.backend = FakeAPIBackend()
        self.client = Juju1APIClient(self.backend.protocol)

    def test_login(self):
        """
        The login method sends a 'Login' request with the provided
        credentials and returns API endpoints information.
        """
        deferred = self.client.login("user-admin", "sekret")
        params = {"AuthTag": "user-admin", "Password": "sekret"}
        self.assertEqual("Admin", self.backend.lastType)
        self.assertEqual("Login", self.backend.lastRequest)
        self.assertIsNone(self.backend.lastVersion)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response(
            {"EnvironTag": "environment-uuid-123",
             "Servers": [
                 [{"NetworkName": "publicnet",
                   "Port": 17070,
                   "Scope": "local-cloud",
                   "Type": "ipv4",
                   "Value": "1.2.3.4"}]]})
        result = self.successResultOf(deferred)
        self.assertEqual(["1.2.3.4:17070"], result.endpoints)
        self.assertEqual("uuid-123", result.uuid)

    def test_modelInfo_good_result(self):
        """
        The modelInfo method sends an 'EnvironmentInfo' request and
        returns a deferred that will callback with a ModelInfo instance.
        """
        uuid = u"a0c03f34-ea02-11e2-8e96-875122dd4b52"
        deferred = self.client.modelInfo(uuid)
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("EnvironmentInfo", self.backend.lastRequest)
        self.assertIsNone(self.backend.lastVersion)
        self.backend.response(
            {u"Name": u"amazon",
             u"ProviderType": u"ec2",
             u"DefaultSeries": u"precise",
             u"UUID": uuid})

        modelInfo = self.successResultOf(deferred)
        self.assertEqual("amazon", modelInfo.name)
        self.assertEqual("ec2", modelInfo.providerType)
        self.assertEqual("precise", modelInfo.defaultSeries)
        self.assertEqual(uuid, modelInfo.uuid)
        self.assertIsNone(modelInfo.controllerUUID)
        self.assertEqual("amazon", modelInfo.cloud)
        self.assertIsNone(modelInfo.cloudRegion)
        self.assertIsNone(modelInfo.cloudCredential)

    def test_modelInfo_bad_result(self):
        """
        _parseModelInfo() fails with an APIRequestError if the result is
        not correctly formed.
        """
        uuid = u"a0c03f34-ea02-11e2-8e96-875122dd4b52"
        deferred = self.client.modelInfo(uuid)
        self.backend.response({})

        err = self.failureResultOf(deferred)
        self.assertIsInstance(err.value, APIRequestError)
        self.assertEqual("malformed result {}", err.value.error)
        self.assertEqual("", err.value.code)

    def test_cloud(self):
        """The cloud method is not supported under Juju 1.x."""
        with self.assertRaises(RuntimeError):
            self.client.cloud("maas")

    def test_watchAll(self):
        """
        The watchAll method sends an 'WatchAll' request and returns a
        deferred that will callback with an allWatcher ID.
        """
        deferred = self.client.watchAll()
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("WatchAll", self.backend.lastRequest)
        self.backend.response({"AllWatcherId": "1"})
        self.assertEqual("1", self.successResultOf(deferred))

    def test_allWatcherNext_machine(self):
        """
        The allWatcherNext method sends a 'Next' request against the given
        allWatcher ID. If the returned response contains a machine, a delta
        with the MachineInfo details will be returned.
        """
        deferred = self.client.allWatcherNext("1")
        self.assertEqual("AllWatcher", self.backend.lastType)
        self.assertEqual("Next", self.backend.lastRequest)
        self.assertEqual("1", self.backend.lastId)
        self.backend.response(
            {u"Deltas": [
                [u"machine", u"change", {
                    u"Id": u"1",
                    u"InstanceId": u"i123",
                    u"Status": u"stopped",
                    u"StatusInfo": u"machine is dead",
                    u"Life": u"dead",
                    u"Jobs": [u"JobManageEnviron", u"JobHostUnits"]}]]})
        [delta] = self.successResultOf(deferred)
        self.assertEqual("machine", delta.kind)
        self.assertEqual("change", delta.verb)
        self.assertEqual("1", delta.info.id)
        self.assertEqual("i123", delta.info.instanceId)
        self.assertEqual("stopped", delta.info.status)
        self.assertEqual("machine is dead", delta.info.statusInfo)
        self.assertEqual(
            [u"JobManageEnviron", u"JobHostUnits"], delta.info.jobs)
        self.assertIsNone(delta.info.hasVote)
        self.assertIsNone(delta.info.wantsVote)

    def test_allWatcherNext_machine_with_HA(self):
        """
        If the response for a machine contains Juju HA flags (HasVote,
        WantsVote), the returned MachineInfo includes them.
        """
        deferred = self.client.allWatcherNext("1")
        self.backend.response(
            {u"Deltas": [
                [u"machine", u"change", {
                    u"Id": u"1",
                    u"InstanceId": u"i123",
                    u"Status": u"pending",
                    u"HasVote": True,
                    u"WantsVote": False}]]})
        [delta] = self.successResultOf(deferred)
        self.assertEqual("machine", delta.kind)
        self.assertEqual("i123", delta.info.instanceId)
        self.assertEqual("pending", delta.info.status)
        self.assertTrue(delta.info.hasVote)
        self.assertFalse(delta.info.wantsVote)

    def test_allWatcherNext_machine_with_usable_endpoint(self):
        """
        If the response contains information about a non-local IPv4 address,
        that it's included in the returned MachineInfo.
        """
        deferred = self.client.allWatcherNext("1")
        self.backend.response(
            {u"Deltas": [
                [u"machine", u"change", {
                    u"Id": u"1",
                    u"InstanceId": u"i123",
                    u"Status": u"pending",
                    u"Addresses": [{
                        "NetworkName": "publicnet",
                        "Scope": "local-cloud",
                        "Type": "ipv4",
                        "Value": "1.2.3.4"}]}]]})
        [delta] = self.successResultOf(deferred)
        self.assertEqual("1.2.3.4", delta.info.address)

    def test_allWatcherNext_machine_with_non_usable_endpoint(self):
        """
        Non-usable network addresses are not included in the returned
        MachineInfo.
        """
        deferred = self.client.allWatcherNext("1")
        self.backend.response(
            {u"Deltas": [
                [u"machine", u"change", {
                    u"Id": u"1",
                    u"InstanceId": u"i123",
                    u"Status": u"pending",
                    u"Addresses": [{
                        "NetworkName": "",
                        "Scope": "local-cloud",
                        "Type": "hostname",
                        "Value": "localhost"}]}]]})
        [delta] = self.successResultOf(deferred)
        self.assertIsNone(delta.info.address)

    def test_allWatcherNext_unit(self):
        """
        The allWatcherNext method sends a 'Next' request against the given
        allWatcher ID. If the returned response contains a unit, a relevant
        WatcherDelta object will be returned.
        """
        deferred = self.client.allWatcherNext("1")
        self.backend.response(
            {u"Deltas": [
                [u"unit", u"change", {
                    u"Name": u"mysql/0",
                    u"Service": u"mysql",
                    u"Series": u"precise",
                    u"CharmURL": u"cs:precise/mysql-9",
                    u"PublicAddress": u"ec2-1-2-3-4.aws.com",
                    u"PrivateAddress": u"ip-1.internal",
                    u"MachineId": u"1",
                    u"Ports": [],
                    u"Status": u"pending",
                    u"StatusInfo": u""}]]})
        [delta] = self.successResultOf(deferred)
        self.assertEqual("unit", delta.kind)
        self.assertEqual("change", delta.verb)
        self.assertEqual("mysql/0", delta.info.name)
        self.assertEqual("mysql", delta.info.applicationName)
        self.assertEqual("precise", delta.info.series)
        self.assertEqual("cs:precise/mysql-9", delta.info.charmURL)
        self.assertEqual("ec2-1-2-3-4.aws.com", delta.info.publicAddress)
        self.assertEqual("ip-1.internal", delta.info.privateAddress)
        self.assertEqual("1", delta.info.machineId)
        self.assertEqual([], delta.info.ports)
        self.assertEqual("pending", delta.info.status)
        self.assertEqual("", delta.info.statusInfo)

    def test_allWatcherNext_service(self):
        """
        The allWatcherNext method sends a 'Next' request against the given
        allWatcher ID. If the returned response contains a unit, a relevant
        WatcherDelta object will be returned.
        """
        deferred = self.client.allWatcherNext("1")
        self.backend.response(
            {u"Deltas": [
                [u"service", u"remove", {
                    u"Name": u"mysql",
                    u"Exposed": False,
                    u"CharmURL": u"local:precise/mysql-9",
                    u"Life": u"alive",
                    u"Constraints": {},
                    u"Config": {u"vip": u"10.0.3.201"}}]]})
        [delta] = self.successResultOf(deferred)
        self.assertEqual("service", delta.kind)
        self.assertEqual("remove", delta.verb)
        self.assertEqual("mysql", delta.info.name)
        self.assertFalse(delta.info.exposed)
        self.assertEqual("alive", delta.info.life)
        self.assertEqual({}, delta.info.constraints)
        self.assertEqual({u"vip": u"10.0.3.201"}, delta.info.config)

    def test_allWatcherNext_annotation(self):
        """
        The allWatcherNext method sends a 'Next' request against the given
        allWatcher ID. If the returned response contains an annotation, a
        relevant AnnotationInfo will be referenced in the returned delta.
        """
        deferred = self.client.allWatcherNext("1")
        self.backend.response(
            {u"Deltas": [
                [u"annotation", u"change", {
                    u"Tag": u"unit-mysql-0",
                    u"Annotations": {u"xx": u"yy"}}]]})
        [delta] = self.successResultOf(deferred)
        self.assertEqual("annotation", delta.kind)
        self.assertEqual("change", delta.verb)
        self.assertEqual("unit", delta.info.entityKind)
        self.assertEqual("mysql/0", delta.info.entityId)
        self.assertEqual({"xx": "yy"}, delta.info.pairs)

    def test_allWatcherNext_action(self):
        """
        The allWatcherNext method sends a 'Next' request against the given
        allWatcher ID. If the returned response contains an action, a
        relevant ActionInfo will be referenced in the returned delta.
        """
        deferred = self.client.allWatcherNext("1")
        self.backend.response(
            {u"Deltas": [
                [u"action", u"change", {
                    u"Completed": u"2015-07-21T07:30:55Z",
                    u"Enqueued": u"2015-07-21T07:30:47Z",
                    u"Id": u"1-2-3",
                    u"Message": u"some message",
                    u"Name": u"do-something",
                    u"Parameters": {},
                    u"Receiver": u"service/2",
                    u"Results": {"foo": "bar"},
                    u"Started": u"2015-07-21T07:30:50Z",
                    u"Status": u"completed"}]]})
        [delta] = self.successResultOf(deferred)
        self.assertEqual("action", delta.kind)
        self.assertEqual("change", delta.verb)
        self.assertEqual("1-2-3", delta.info.id)
        self.assertEqual("do-something", delta.info.name)
        self.assertEqual("service/2", delta.info.receiver)
        self.assertEqual("completed", delta.info.status)
        self.assertEqual("some message", delta.info.message)
        self.assertEqual({"foo": "bar"}, delta.info.results)

    def test_AllWatcherStoppedError_raised(self):
        """
        If the allWatcher is stopped an AllWatcherStoppedError is raised.
        """
        deferred = self.client.allWatcherNext("1")
        self.backend.error(APIRequestError("watcher was stopped", ""))
        failure = self.failureResultOf(deferred)
        self.assertIsInstance(failure.value, AllWatcherStoppedError)

    def test_other_errors_reraised(self):
        """
        If allWatcherNext receives a different error it is re-raised.
        """
        deferred = self.client.allWatcherNext("1")
        self.backend.error(
            APIRequestError("Quis custodiet ipsos custodes?", ""))
        failure = self.failureResultOf(deferred)
        self.assertIsInstance(failure.value, APIRequestError)

    def test_setAnnotations(self):
        """
        The setAnnotations method sends a 'setAnnotations' request with
        the given tags.
        """
        deferred = self.client.setAnnotations("unit", "1", {"foo": "bar"})
        params = {"Tag": "unit-1", "Pairs": {"foo": "bar"}}
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("SetAnnotations", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.assertIsNone(self.backend.lastVersion)
        self.backend.response({})
        self.assertIsNone(self.successResultOf(deferred))

    def test_serviceGet(self):
        """
        The serviceGet method sends a 'serviceGet' request for getting
        the config of the service with the given name.
        """
        deferred = self.client.serviceGet("keystone")
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("ServiceGet", self.backend.lastRequest)
        self.assertEqual({"ServiceName": "keystone"}, self.backend.lastParams)
        self.assertIsNone(self.backend.lastVersion)
        self.backend.response(
            {u"Service": u"keystone",
             u"Charm": u"keystone",
             u"Constraints": {},
             u"Config": {u"admin-password": {u"default": True,
                                             u"description": u"Admin password",
                                             u"type": u"string",
                                             u"value": u"sekret"},
                         u"admin-port": {u"default": True,
                                         u"description": u"Port of Admin API",
                                         u"type": u"int",
                                         u"value": 35357}}})

        config = self.successResultOf(deferred)
        self.assertEqual("keystone", config.application)
        self.assertEqual("keystone", config.charm)
        self.assertTrue(config.has_options(["admin-password", "admin-port"]))
        self.assertEqual("sekret", config.get_value("admin-password"))
        self.assertEqual(35357, config.get_value("admin-port"))

    def test_serviceSet(self):
        """
        The serviceSet method sends a 'serviceSet' request for setting
        the config of the service with the given name.
        """
        deferred = self.client.serviceSet("keystone", {"foo": "bar"})
        params = {"ServiceName": "keystone", "Options": {"foo": "bar"}}
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("ServiceSet", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.assertIsNone(self.backend.lastVersion)
        self.backend.response({})
        self.successResultOf(deferred)

    def test_serviceDeploy(self):
        """
        The serviceDeploy method sends a 'ServiceDeploy' request for
        deploying a service with the given name, charm, number of
        units, and charm configuration.

        Since scope and directive are not passed, NumUnits is 0 - it's a
        subordinate.
        """
        deferred = self.client.serviceDeploy(
            serviceName="ceph", charmURL="cs:precise/ceph-18",
            config={
                "monitor-count": "3",
                "fsid": "6547bd3e-1397-11e2-82e5-53567c8d32dc",
                "monitor-secret": "AQCXrnZQwI7KGBAAiPofmKEXKxu5bUzoYLVkbQ==",
                "osd-devices": "/dev/vdb",
                "osd-reformat": "yes",
                "ephemeral-unmount": "/mnt"})
        params = {"ServiceName": "ceph",
                  "CharmURL": "cs:precise/ceph-18",
                  "NumUnits": 0,
                  "ConfigYAML": yaml.dump(
                      {"ceph": {
                          "monitor-count": "3",
                          "fsid": "6547bd3e-1397-11e2-82e5-53567c8d32dc",
                          "monitor-secret": (
                              "AQCXrnZQwI7KGBAAiPofmKEXKxu5bUzoYLVkbQ=="),
                          "osd-devices": "/dev/vdb",
                          "osd-reformat": "yes",
                          "ephemeral-unmount": "/mnt"}})}
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("ServiceDeploy", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response({})
        self.assertIsNone(self.successResultOf(deferred))

    def test_serviceDeploy_with_placement(self):
        """
        The serviceDeploy method sends a 'ServiceDeploy' request with an
        optional ToMachineSpec parameter when passed.
        """
        deferred = self.client.serviceDeploy(
            serviceName="ceph", charmURL="cs:precise/ceph-18",
            directive="1/lxc/2",
            config={
                "monitor-count": "3",
                "fsid": "6547bd3e-1397-11e2-82e5-53567c8d32dc",
                "monitor-secret": "AQCXrnZQwI7KGBAAiPofmKEXKxu5bUzoYLVkbQ==",
                "osd-devices": "/dev/vdb",
                "osd-reformat": "yes",
                "ephemeral-unmount": "/mnt"})
        params = {"ServiceName": "ceph",
                  "CharmURL": "cs:precise/ceph-18",
                  "NumUnits": 1,
                  "ToMachineSpec": "1/lxc/2",
                  "ConfigYAML": yaml.dump(
                      {"ceph": {
                          "monitor-count": "3",
                          "fsid": "6547bd3e-1397-11e2-82e5-53567c8d32dc",
                          "monitor-secret": (
                              "AQCXrnZQwI7KGBAAiPofmKEXKxu5bUzoYLVkbQ=="),
                          "osd-devices": "/dev/vdb",
                          "osd-reformat": "yes",
                          "ephemeral-unmount": "/mnt"}})}
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response({})
        self.assertIsNone(self.successResultOf(deferred))

    def test_serviceDeploy_no_optionals(self):
        """
        The serviceDeploy method sends a 'ServiceDeploy' request for
        deploying a service with the given name and charm, filling in the
        optional parameters with defaults.
        Since scope and directive are not passed, NumUnits is 0 - it's a
        subordinate.
        """
        deferred = self.client.serviceDeploy(
            serviceName="ceph", charmURL="cs:precise/ceph-18")
        params = {"ServiceName": "ceph",
                  "CharmURL": "cs:precise/ceph-18",
                  "NumUnits": 0,
                  "ConfigYAML": yaml.dump({"ceph": {}})}
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response({})
        self.assertIsNone(self.successResultOf(deferred))

    def test_addRelation(self):
        """
        The addRelation method sends a 'AddRelation' request to add a
        Juju relation between two endpoints, specified by endpoint name.
        """
        deferred = self.client.addRelation("mysql:db", "wordpress:db")
        params = {"Endpoints": ["mysql:db", "wordpress:db"]}

        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("AddRelation", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.assertIsNone(self.backend.lastVersion)
        self.backend.response({})
        self.assertIsNone(self.successResultOf(deferred))

    def test_addMachine(self):
        """
        The addMachine method sends a 'AddMachines' request version 0 to add a
        Juju machine with the specified MAAS name.
        """
        deferred = self.client.addMachine(
            scope=u"uuid1", directive=u"maas-name")
        params = {"MachineParams": [{"Jobs": ["JobHostUnits"],
                                     "Placement": {
                                         u"Directive": u"maas-name",
                                         u"Scope": u"uuid1"}}]}

        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("AddMachines", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.assertIsNone(self.backend.lastVersion)
        self.backend.response(
            {u'Machines': [{u'Error': None, u'Machine': u'1'}]})
        self.assertEqual("1", self.successResultOf(deferred))

    def test_addMachine_no_placement(self):
        """
        If no scope/directive parameters are passed, the addMachine method
        doesn't specify any placement for the machine.
        Juju machine with the specified MAAS name.
        """
        deferred = self.client.addMachine()
        params = {"MachineParams": [{"Jobs": ["JobHostUnits"]}]}
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("AddMachines", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response(
            {u'Machines': [{u'Error': None, u'Machine': u'1'}]})
        self.assertEqual("1", self.successResultOf(deferred))

    def test_addMachine_with_parentId(self):
        """
        When parentId parameter is passed, the addMachine method targets a
        container of type lxc on the specified juju machine.
        """
        deferred = self.client.addMachine(parentId=1)
        params = {"MachineParams": [{
            "Jobs": ["JobHostUnits"], "ParentId": 1, "ContainerType": "lxc"}]}
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("AddMachines", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response(
            {u'Machines': [{u'Error': None, u'Machine': u'1'}]})
        self.assertEqual("1", self.successResultOf(deferred))

    def test_close(self):
        """
        The close method terminates the connection.
        """
        assert self.backend.connected
        self.successResultOf(self.client.close())
        self.assertFalse(self.backend.connected)

    def test_addUnit(self):
        """
        The addUnit method sends an 'AddServiceUnits' Juju 1.X request with
        NumUnits set to 1 and the passed in service name and placement
        directive.
        """
        deferred = self.client.addUnit(
            serviceName="ceph", scope=MACHINE_SCOPE, directive="1/lxc/2")
        params = {"ServiceName": "ceph",
                  "NumUnits": 1,
                  "ToMachineSpec": "1/lxc/2"}
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("AddServiceUnits", self.backend.lastRequest)
        self.assertIsNone(self.backend.lastVersion)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response({"Units": ["ceph/0"]})
        self.assertEqual("ceph/0", self.successResultOf(deferred))

    def test_run(self):
        """
        The run method sends a 'Run' request with the passed in command
        and timeout to the given units.

        It returns a dict of useful information keyed by unit names.
        """
        deferred = self.client.run(
            commands="ls /home", timeout=timedelta(seconds=10),
            units=["landscape/0", "ubuntu/2"])
        params = {"Commands": "ls /home",
                  "Timeout": 10000000000,
                  "Units": ["landscape/0", "ubuntu/2"]}
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("Run", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response({
            u'Results': [{u'Code': 0,
                          u'Error': u'',
                          u'MachineId': u'',
                          u'Stderr': u'',
                          u'Stdout': u'dWJ1bnR1Cg==',
                          u'UnitId': u'landscape/0'},
                         {u'Code': 0,
                          u'Error': u'',
                          u'MachineId': u'',
                          u'Stderr': u'',
                          u'Stdout': u'dWJ1bnR1Cg==',
                          u'UnitId': u'ubuntu/2'}]})
        result = self.successResultOf(deferred)

        self.assertItemsEqual(["landscape/0", "ubuntu/2"], result.keys())
        self.assertEqual("ubuntu\n", result["landscape/0"].stdout)
        self.assertEqual("", result["landscape/0"].stderr)
        self.assertEqual(0, result["landscape/0"].code)
        self.assertEqual("", result["landscape/0"].error)

    def test_run_default_timeout(self):
        """
        The run method has an optional timeout parameter which defaults to 5m.
        """
        deferred = self.client.run(commands="ls /home", units=[])
        params = {"Commands": "ls /home",
                  "Timeout": 300000000000,
                  "Units": []}
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("Run", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response({"Results": []})
        self.successResultOf(deferred)

    def test_runOnAllMachines(self):
        """The runOnAllMachines method sends a 'RunOnAllMachines' request
        passing a command and timeout.

        It returns a dict of useful information keyed by machine names.
        """
        deferred = self.client.runOnAllMachines(
            commands="ls /home", timeout=timedelta(seconds=10))
        params = {"Commands": "ls /home", "Timeout": 10000000000}
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("RunOnAllMachines", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response({
            u'Results': [{u'Code': 0,
                          u'Error': u'',
                          u'MachineId': u'0',
                          u'Stderr': u'',
                          u'Stdout': u'dWJ1bnR1Cg==',
                          u'UnitId': u''},
                         {u'Code': 0,
                          u'Error': u'',
                          u'MachineId': u'0/lxc/1',
                          u'Stderr': u'',
                          u'Stdout': u'dWJ1bnR1Cg==',
                          u'UnitId': u''}]})
        result = self.successResultOf(deferred)

        self.assertItemsEqual(["0", "0/lxc/1"], result.keys())
        self.assertEqual("ubuntu\n", result["0"].stdout)
        self.assertEqual("", result["0"].stderr)
        self.assertEqual(0, result["0"].code)
        self.assertEqual("", result["0"].error)

    def test_runOnAllMachines_default_timeout(self):
        """
        The runOnAllMachines method has an optional timeout parameter
        which defaults to 5m.
        """
        deferred = self.client.runOnAllMachines(commands="ls /home")
        params = {"Commands": "ls /home",
                  "Timeout": 300000000000}
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("RunOnAllMachines", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response({"Results": []})
        self.successResultOf(deferred)

    def test_enqueueAction(self):
        """
        The enqueueAction method performs a call to enqueue an action on a
        unit and returns the action Id.
        """
        deferred = self.client.enqueueAction("do-stuff", "service/2")
        self.assertEqual("Action", self.backend.lastType)
        self.assertEqual("Enqueue", self.backend.lastRequest)
        self.assertIsNone(self.backend.lastVersion)
        self.assertEqual(
            {"Actions": [
                {"Parameters": {}, "Name": "do-stuff",
                 "Receiver": "unit-service-2"}]},
            self.backend.lastParams)
        self.backend.response(
            {"results": [
                {"action": {
                    "name": "do-stuff",
                    "receiver": "service-2",
                    "tag": "action-a-2-3"},
                 "completed": "0001-01-01T00:00:00Z",
                 "enqueued": "2015-07-20T08:02:10Z",
                 "started": "0001-01-01T00:00:00Z",
                 "status": "pending"}]})
        self.assertEqual("a-2-3", self.successResultOf(deferred))

    def test_enqueueAction_parameters(self):
        """It's possible to pass parameters to the action."""
        parameters = {"param1": "foo", "param2": "bar"}
        self.client.enqueueAction(
            "do-stuff", "service/2", parameters=parameters)
        self.assertEqual(
            parameters, self.backend.lastParams["Actions"][0]["Parameters"])

    def test_enqueueAction_failure(self):
        """If the action fails, an APIRequestError is raised."""
        parameters = {"param1": "foo", "param2": "bar"}
        deferred = self.client.enqueueAction(
            "do-stuff", "service/2", parameters=parameters)
        self.backend.response(
            {"results": [
                {"error": {
                    "Message": "Boom!",
                    "Code": "boom"}}]})
        failure = self.failureResultOf(deferred)
        self.assertIsInstance(failure.value, APIRequestError)
        self.assertEqual("Boom!", failure.value.error)
        self.assertEqual("boom", failure.value.code)


class Juju2APIClientTest(TestCase):
    """Test Juju2APIClient."""

    def setUp(self):
        super(Juju2APIClientTest, self).setUp()
        self.backend = FakeAPIBackend()
        self.client = Juju2APIClient(self.backend.protocol)

    def test_login(self):
        """
        The login method sends a 'Login' version 3 request with the provided
        credentials and returns API endpoints information and parses the
        appropriate version 3 response.
        """
        deferred = self.client.login("user-admin", "sekret")
        params = {"auth-tag": "user-admin", "credentials": "sekret"}
        self.assertEqual("Admin", self.backend.lastType)
        self.assertEqual("Login", self.backend.lastRequest)
        self.assertEqual(3, self.backend.lastVersion)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response(
            {"model-tag": "model-uuid-123",
             "servers": [
                 [{"space-name": "some-space-0",
                   "port": 17070,
                   "scope": "local-cloud",
                   "type": "ipv4",
                   "value": "1.2.3.4"}]]})
        result = self.successResultOf(deferred)
        self.assertEqual(["1.2.3.4:17070"], result.endpoints)
        self.assertEqual("uuid-123", result.uuid)

    def test_login_username_tag(self):
        """
        If the username is a user tag then it is used as-is.
        """
        self.client.login("user-admin", "sekret")

        params = {"auth-tag": "user-admin", "credentials": "sekret"}
        self.assertEqual(params, self.backend.lastParams)

    def test_login_username_not_tag(self):
        """
        If the username is not a user tag then it is turned into one.
        """
        self.client.login("admin", "sekret")

        params = {"auth-tag": "user-admin", "credentials": "sekret"}
        self.assertEqual(params, self.backend.lastParams)

    def test_modelInfo(self):
        """
        The modelInfo method sends a 'ModelInfo' request and
        returns a deferred that will callback with a ModelInfo instance.
        """
        uuid = u"a0c03f34-ea02-11e2-8e96-875122dd4b52"
        deferred = self.client.modelInfo(uuid)
        self.assertEqual("ModelManager", self.backend.lastType)
        self.assertEqual("ModelInfo", self.backend.lastRequest)
        self.assertEqual(2, self.backend.lastVersion)
        self.assertEqual({"entities": [{"tag": "model-" + uuid}]},
                         self.backend.lastParams)
        self.backend.response(
            {"results": [{"result": {
                u"name": u"my-maas",
                u"provider-type": u"maas",
                u"default-series": u"precise",
                u"uuid": uuid,
                u"controller-uuid": u"a0c03f34-ea02-11e2-8e96-875122dd4b53",
                u"cloud": "maas1",
                u"cloud-region": "1",
                u"cloud-credential": "abc123...",
                }}],
             })

        modelInfo = self.successResultOf(deferred)
        self.assertEqual("my-maas", modelInfo.name)
        self.assertEqual("maas", modelInfo.providerType)
        self.assertEqual("precise", modelInfo.defaultSeries)
        self.assertEqual(uuid, modelInfo.uuid)
        self.assertEqual(
            "a0c03f34-ea02-11e2-8e96-875122dd4b53", modelInfo.controllerUUID)
        self.assertEqual("maas1", modelInfo.cloud)
        self.assertEqual("1", modelInfo.cloudRegion)
        self.assertEqual("abc123...", modelInfo.cloudCredential)

    def test_modelInfo_bad_response(self):
        """
        _parseModelInfo() fails with an APIRequestError if the response is
        not correctly formed.
        """
        uuid = u"a0c03f34-ea02-11e2-8e96-875122dd4b52"
        deferred = self.client.modelInfo(uuid)
        self.backend.response({"spam": []})

        err = self.failureResultOf(deferred)
        self.assertIsInstance(err.value, APIRequestError)
        self.assertEqual("malformed response {u'spam': []}", err.value.error)
        self.assertEqual("", err.value.code)

    def test_modelInfo_no_results(self):
        """
        _parseModelInfo() fails with an APIRequestError if there aren't any
        results.
        """
        uuid = u"a0c03f34-ea02-11e2-8e96-875122dd4b52"
        deferred = self.client.modelInfo(uuid)
        self.backend.response({"results": []})

        err = self.failureResultOf(deferred)
        self.assertIsInstance(err.value, APIRequestError)
        self.assertEqual("expected 1 result, got none", err.value.error)
        self.assertEqual("", err.value.code)

    def test_modelInfo_multiple_results(self):
        """
        _parseModelInfo() fails with an APIRequestError if there is more
        than one result.
        """
        uuid = u"a0c03f34-ea02-11e2-8e96-875122dd4b52"
        deferred = self.client.modelInfo(uuid)
        self.backend.response({"results": [{}, {}]})

        err = self.failureResultOf(deferred)
        self.assertIsInstance(err.value, APIRequestError)
        self.assertEqual("expected 1 result, got 2", err.value.error)
        self.assertEqual("", err.value.code)

    def test_modelInfo_error_result(self):
        """
        _parseModelInfo() fails with an APIRequestError if the result has
        an error set.
        """
        uuid = u"a0c03f34-ea02-11e2-8e96-875122dd4b52"
        deferred = self.client.modelInfo(uuid)
        self.backend.response({"results": [{"error": {
            u"message": "model {} not found".format(uuid),
            u"code": "not found",
            }}]})

        err = self.failureResultOf(deferred)
        self.assertIsInstance(err.value, APIRequestError)
        self.assertEqual("model {} not found".format(uuid), err.value.error)
        self.assertEqual("not found", err.value.code)

    def test_modelInfo_bad_result(self):
        """
        _parseModelInfo() fails with an APIRequestError if the result is
        not correctly formed.
        """
        uuid = u"a0c03f34-ea02-11e2-8e96-875122dd4b52"
        deferred = self.client.modelInfo(uuid)
        self.backend.response({"results": [{"result": {}}]})

        err = self.failureResultOf(deferred)
        self.assertIsInstance(err.value, APIRequestError)
        self.assertEqual("malformed result {}", err.value.error)
        self.assertEqual("", err.value.code)

    def test_cloud_full(self):
        """
        The cloud method sends a 'Cloud' request and
        returns a deferred that will callback with a CloudInfo instance.
        """
        deferred = self.client.cloud("maas")
        self.assertEqual("Cloud", self.backend.lastType)
        self.assertEqual("Cloud", self.backend.lastRequest)
        self.assertEqual(1, self.backend.lastVersion)
        self.assertEqual(
            {"entities": [{"tag": "cloud-maas"}]}, self.backend.lastParams)
        region = {"endpoint": "https://10.1.2.3/MAAS/1",
                  "storage-endpoint": "https://10.1.2.3/MAAS/1/storage"}
        self.backend.response(
            {u"results": [
                {u"cloud": {u"type": u"maas",
                            u"auth-types": ["spam"],
                            u"endpoint": u"https://10.1.2.3/MAAS",
                            u"storage-endpoint":
                                u"https://10.1.2.3/MAAS/storage",
                            u"regions": [region],
                            }},
                ]})

        cloudInfo = self.successResultOf(deferred)
        self.assertEqual("maas", cloudInfo.cloudtype)
        self.assertListEqual(["spam"], cloudInfo.authTypes)
        self.assertEqual("https://10.1.2.3/MAAS", cloudInfo.endpoint)
        self.assertEqual(
            "https://10.1.2.3/MAAS/storage", cloudInfo.storageEndpoint)
        self.assertListEqual([region], cloudInfo.regions)

    def test_cloud_minimal(self):
        """
        The cloud method sends a 'Cloud' request and
        returns a deferred that will callback with a CloudInfo instance.

        Juju's API may omit all the response values (except "type").
        """
        deferred = self.client.cloud("maas")
        self.assertEqual("Cloud", self.backend.lastType)
        self.assertEqual("Cloud", self.backend.lastRequest)
        self.assertEqual(1, self.backend.lastVersion)
        self.assertEqual(
            {"entities": [{"tag": "cloud-maas"}]}, self.backend.lastParams)
        self.backend.response({u"results": [{u"cloud": {u"type": u"maas"}}]})

        cloudInfo = self.successResultOf(deferred)
        self.assertEqual("maas", cloudInfo.cloudtype)
        self.assertListEqual([], cloudInfo.authTypes)
        self.assertIsNone(cloudInfo.endpoint)
        self.assertIsNone(cloudInfo.storageEndpoint)
        self.assertListEqual([], cloudInfo.regions)

    def test_runOnAllMachines(self):
        """The runOnAllMachines method sends a 'RunOnAllMachines' request
        passing a command and timeout.

        It returns a list of ActionInfo objects containing the pending action
        ids.
        """
        deferred = self.client.runOnAllMachines(
            commands="ls /home", timeout=timedelta(seconds=10))
        params = {"commands": "ls /home", "timeout": 10000000000}
        self.assertEqual("Action", self.backend.lastType)
        self.assertEqual("RunOnAllMachines", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response({
            u'results': [{u'action': {u'tag': u'action-1'}},
                         {u'action': {u'tag': u'action-2'}}]})
        result = self.successResultOf(deferred)
        self.assertItemsEqual(["1", "2"], result)

    def test_runOnAllMachines_failure(self):
        """If the RunOnAllMachines fails, an APIRequestError is raised."""
        deferred = self.client.runOnAllMachines(
            commands="ls /home", timeout=timedelta(seconds=10))
        self.backend.response(
            {"results": [
                {"error": {
                    "message": "Boom!",
                    "code": "boom"}}]})
        failure = self.failureResultOf(deferred)
        self.assertIsInstance(failure.value, APIRequestError)
        self.assertEqual("Boom!", failure.value.error)
        self.assertEqual("boom", failure.value.code)

    def test_destroyMachines(self):
        """
        The destroyMachines method sends a "Client" "DestroyMachines" request
        to release the machines and any hosted containers from the juju model.
        """
        deferred = self.client.destroyMachines([1, 2])
        params = {"force": True, "machine-names": ["1", "2"]}
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("DestroyMachines", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.assertEqual(1, self.backend.lastVersion)
        self.backend.response({})  # Successful response is empty
        self.successResultOf(deferred)

    def test_applicationDestroy(self):
        """
        The applicationDestroy method sends a "Application" "Destroy" request
        for the named application to completely remove it from the juju model.
        """
        deferred = self.client.applicationDestroy("keystone")
        params = {"application": "keystone"}
        self.assertEqual("Application", self.backend.lastType)
        self.assertEqual("Destroy", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.assertEqual(1, self.backend.lastVersion)
        self.backend.response({})
        self.successResultOf(deferred)

    def test_serviceGet(self):
        """
        The serviceGet method sends an "Application" "Get" request for getting
        the config of the application with the given name.
        """
        deferred = self.client.serviceGet("keystone")
        params = {"application": "keystone"}
        self.assertEqual("Application", self.backend.lastType)
        self.assertEqual("Get", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.assertEqual(1, self.backend.lastVersion)
        self.backend.response(
            {u"application": u"keystone",
             u"charm": u"keystone",
             u"constraints": {},
             u"config": {u"admin-password": {u"default": True,
                                             u"description": u"Admin password",
                                             u"type": u"string",
                                             u"value": u"sekret"},
                         u"admin-port": {u"default": True,
                                         u"description": u"Port of Admin API",
                                         u"type": u"int",
                                         u"value": 35357}}})

        config = self.successResultOf(deferred)
        self.assertEqual("keystone", config.application)
        self.assertEqual("keystone", config.charm)
        self.assertTrue(config.has_options(["admin-password", "admin-port"]))
        self.assertEqual("sekret", config.get_value("admin-password"))
        self.assertEqual(35357, config.get_value("admin-port"))

    def test_serviceSet(self):
        """
        The serviceSet method sends a "Service" "Set" request for setting
        the config of the service with the given name.
        """
        deferred = self.client.serviceSet("keystone", {"foo": "bar"})
        params = {"application": "keystone", "options": {"foo": "bar"}}
        self.assertEqual("Application", self.backend.lastType)
        self.assertEqual("Set", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.assertEqual(1, self.backend.lastVersion)
        self.backend.response({})
        self.successResultOf(deferred)

    def test_serviceDeploy(self):
        """
        The serviceDeploy method sends a 'Deploy' request to the 'Application'
        facade thus deploying a service with the given name, charm, number of
        units, and charm configuration.

        Since scope and directive are not passed, NumUnits is 0 - it's a
        subordinate.
        """
        deferred = self.client.serviceDeploy(
            serviceName="ceph", charmURL="cs:precise/ceph-18",
            config={
                "monitor-count": "3",
                "fsid": "6547bd3e-1397-11e2-82e5-53567c8d32dc",
                "monitor-secret": "AQCXrnZQwI7KGBAAiPofmKEXKxu5bUzoYLVkbQ==",
                "osd-devices": "/dev/vdb",
                "osd-reformat": "yes",
                "ephemeral-unmount": "/mnt"})
        params = {
            "applications": [
                {"application": "ceph",
                 "charm-url": "cs:precise/ceph-18",
                 "channel": "stable",
                 "num-units": 0,
                 "config-yaml": yaml.dump(
                     {"ceph": {
                         "monitor-count": "3",
                         "fsid": "6547bd3e-1397-11e2-82e5-53567c8d32dc",
                         "monitor-secret": (
                             "AQCXrnZQwI7KGBAAiPofmKEXKxu5bUzoYLVkbQ=="),
                         "osd-devices": "/dev/vdb",
                         "osd-reformat": "yes",
                         "ephemeral-unmount": "/mnt"}})}]
        }
        self.assertEqual("Application", self.backend.lastType)
        self.assertEqual("Deploy", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response({})
        self.assertIsNone(self.successResultOf(deferred))

    def test_serviceDeploy_with_machine_spec(self):
        """
        The serviceDeploy method sends a 'ServiceDeploy' request with an
        optional Placement parameter when directive is passed.
        """
        deferred = self.client.serviceDeploy(
            serviceName="ceph", charmURL="cs:precise/ceph-18",
            directive="1/lxc/2",
            config={
                "monitor-count": "3",
                "fsid": "6547bd3e-1397-11e2-82e5-53567c8d32dc",
                "monitor-secret": "AQCXrnZQwI7KGBAAiPofmKEXKxu5bUzoYLVkbQ==",
                "osd-devices": "/dev/vdb",
                "osd-reformat": "yes",
                "ephemeral-unmount": "/mnt"})
        params = {
            "applications": [
                {"application": "ceph",
                 "charm-url": "cs:precise/ceph-18",
                 "channel": "stable",
                 "num-units": 1,
                 "placement": [{"scope": "#", "directive": "1/lxc/2"}],
                 "config-yaml": yaml.dump(
                     {"ceph": {
                         "monitor-count": "3",
                         "fsid": "6547bd3e-1397-11e2-82e5-53567c8d32dc",
                         "monitor-secret": (
                             "AQCXrnZQwI7KGBAAiPofmKEXKxu5bUzoYLVkbQ=="),
                         "osd-devices": "/dev/vdb",
                         "osd-reformat": "yes",
                         "ephemeral-unmount": "/mnt"}})}]}
        self.assertEqual(params, self.backend.lastParams)
        self.assertEqual(1, self.backend.lastVersion)
        self.backend.response({})
        self.assertIsNone(self.successResultOf(deferred))

    def test_serviceDeploy_with_machine_spec_new_lxc(self):
        """
        The serviceDeploy method sends a 'ServiceDeploy' request with an
        optional Placement parameter defining an 'lxc' scope when a new lxc on
        an existing machine is requested using the machine_spec param.
        """
        deferred = self.client.serviceDeploy(
            serviceName="ceph", charmURL="cs:precise/ceph-18",
            scope="lxc",
            directive="2",  # Request new lxc on machine 2
            config={
                "monitor-count": "3",
                "fsid": "6547bd3e-1397-11e2-82e5-53567c8d32dc",
                "monitor-secret": "AQCXrnZQwI7KGBAAiPofmKEXKxu5bUzoYLVkbQ==",
                "osd-devices": "/dev/vdb",
                "osd-reformat": "yes",
                "ephemeral-unmount": "/mnt"})
        params = {
            "applications": [
                {"application": "ceph",
                 "charm-url": "cs:precise/ceph-18",
                 "channel": "stable",
                 "num-units": 1,
                 "placement": [{"scope": "lxc", "directive": "2"}],
                 "config-yaml": yaml.dump(
                     {"ceph": {
                         "monitor-count": "3",
                         "fsid": "6547bd3e-1397-11e2-82e5-53567c8d32dc",
                         "monitor-secret": (
                             "AQCXrnZQwI7KGBAAiPofmKEXKxu5bUzoYLVkbQ=="),
                         "osd-devices": "/dev/vdb",
                         "osd-reformat": "yes",
                         "ephemeral-unmount": "/mnt"}})}]}
        self.assertEqual(params, self.backend.lastParams)
        self.assertEqual(1, self.backend.lastVersion)
        self.backend.response({})
        self.assertIsNone(self.successResultOf(deferred))

    def test_addMachine(self):
        """
        The addMachine method sends a 'AddMachines' request version 1 to add a
        Juju machine with the specified MAAS name.
        """
        deferred = self.client.addMachine(
            scope=u"uuid1", directive=u"maas-name")
        params = {"params": [{"jobs": ["JobHostUnits"],
                              "placement": {"directive": u"maas-name",
                                            "scope": "uuid1"}}]}

        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("AddMachines", self.backend.lastRequest)
        self.assertEqual(1, self.backend.lastVersion)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response(
            {u'machines': [{u'Error': None, u'machine': u'1'}]})
        self.assertEqual("1", self.successResultOf(deferred))

    def test_addMachine_with_series(self):
        """
        The addMachine method sends the Ubuntu series, if provided.
        """
        self.client.addMachine(
            scope=u"uuid1", directive=u"maas-name", ubuntu_series=u"trusty")

        params = {"params": [{"jobs": ["JobHostUnits"],
                              "series": u"trusty",
                              "placement": {"directive": u"maas-name",
                                            "scope": "uuid1"}}]}
        self.assertEqual(params, self.backend.lastParams)

    def test_addCharm(self):
        """
        The addCharm method sends an 'AddCharm' version 1 request with the
        provided charmURL parameter and parses the version 1 response.
        """
        deferred = self.client.addCharm("cs:trusty/trinket")
        params = {"url": "cs:trusty/trinket"}
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("AddCharm", self.backend.lastRequest)
        self.assertEqual(1, self.backend.lastVersion)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response({})
        self.assertIsNone(self.successResultOf(deferred))

    def test_addCharm_with_error(self):
        """
        The addCharm method raises an APIRequestError when the API response
        contains an error.
        """
        deferred = self.client.addCharm("cs:trusty/absent-charm")
        self.backend.response({"Error": "Boom!"})
        failure = self.failureResultOf(deferred)
        self.assertIsInstance(failure.value, APIRequestError)
        self.assertEqual("Boom!", failure.value.error)
        self.assertEqual("", failure.value.code)

    def test_addUnit(self):
        """
        The addUnit method sends an 'AddUnits' request with
        NumUnits set to 1 and Placement set to MACHINE_SCOPE when service
        name and a machine directive are provided.
        """
        deferred = self.client.addUnit(
            serviceName="ceph", scope=None, directive="1/lxc/2")
        params = {"application": "ceph",
                  "num-units": 1,
                  "placement": [{"scope": "#", "directive": "1/lxc/2"}]}
        self.assertEqual("Application", self.backend.lastType)
        self.assertEqual("AddUnits", self.backend.lastRequest)
        self.assertEqual(1, self.backend.lastVersion)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response({"units": ["ceph/0"]})
        self.assertEqual("ceph/0", self.successResultOf(deferred))

    def test_setAnnotations(self):
        """
        The setAnnotations method sends an "Annotations" "Set" request with
        the given tags.
        """
        deferred = self.client.setAnnotations("unit", "1", {"foo": "bar"})
        params = {"annotations": [
            {"entity": "unit-1", "annotations": {"foo": "bar"}}]}
        self.assertEqual("Annotations", self.backend.lastType)
        self.assertEqual("Set", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.assertEqual(2, self.backend.lastVersion)
        self.backend.response({})
        self.assertIsNone(self.successResultOf(deferred))

    def test_addRelation(self):
        """
        The addRelation method sends a 'AddRelation' request to add a
        Juju relation between two endpoints, specified by endpoint name.
        """
        deferred = self.client.addRelation("mysql:db", "wordpress:db")
        params = {"Endpoints": ["mysql:db", "wordpress:db"]}

        self.assertEqual("Application", self.backend.lastType)
        self.assertEqual("AddRelation", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.assertEqual(1, self.backend.lastVersion)
        self.backend.response({})
        self.assertIsNone(self.successResultOf(deferred))

    def test_watchAll(self):
        """
        The watchAll method sends an 'WatchAll' request and returns a
        deferred that will callback with an allWatcher ID.
        """
        deferred = self.client.watchAll()
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("WatchAll", self.backend.lastRequest)
        self.assertEqual(1, self.backend.lastVersion)
        self.backend.response({"watcher-id": "1"})
        self.assertEqual("1", self.successResultOf(deferred))

    def test_allWatcherNext_machine(self):
        """
        The allWatcherNext method sends a 'Next' request against the given
        allWatcher ID. If the returned response contains a machine, a delta
        with the MachineInfo details will be returned.
        """
        deferred = self.client.allWatcherNext("1")
        self.assertEqual("AllWatcher", self.backend.lastType)
        self.assertEqual("Next", self.backend.lastRequest)
        self.assertEqual(1, self.backend.lastVersion)
        self.assertEqual("1", self.backend.lastId)
        self.backend.response(
            {u"deltas": [
                [u"machine", u"change", {
                    u"id": u"1",
                    u"instance-id": u"i123",
                    u"agent-status": {
                        u"current": u"stopped",
                        u"message": u"machine is dead",
                    },
                    u"life": u"dead",
                    u"jobs": [u"JobManageModel", u"JobHostUnits"]}]]})
        [delta] = self.successResultOf(deferred)
        self.assertEqual("machine", delta.kind)
        self.assertEqual("change", delta.verb)
        self.assertEqual("1", delta.info.id)
        self.assertEqual("i123", delta.info.instanceId)
        self.assertEqual("stopped", delta.info.status)
        self.assertEqual("machine is dead", delta.info.statusInfo)
        self.assertEqual(
            [u"JobManageModel", u"JobHostUnits"], delta.info.jobs)
        self.assertIsNone(delta.info.hasVote)
        self.assertIsNone(delta.info.wantsVote)

    def test_enqueueAction(self):
        """
        The enqueueAction method performs a call to enqueue an action on a
        unit and returns the action Id.
        """
        deferred = self.client.enqueueAction("do-stuff", "service/2")
        self.assertEqual("Action", self.backend.lastType)
        self.assertEqual("Enqueue", self.backend.lastRequest)
        self.assertEqual(2, self.backend.lastVersion)
        self.assertEqual(
            {"actions": [
                {"parameters": {}, "name": "do-stuff",
                 "receiver": "unit-service-2"}]},
            self.backend.lastParams)
        self.backend.response(
            {"results": [
                {"action": {
                    "name": "do-stuff",
                    "receiver": "service-2",
                    "tag": "action-a-2-3"},
                 "completed": "0001-01-01T00:00:00Z",
                 "enqueued": "2015-07-20T08:02:10Z",
                 "started": "0001-01-01T00:00:00Z",
                 "status": "pending"}]})
        self.assertEqual("a-2-3", self.successResultOf(deferred))

    def test_addMachine_with_parentId(self):
        """
        When parentId parameter is passed, the addMachine method targets a
        container of type lxd on the specified juju machine.
        """
        deferred = self.client.addMachine(parentId=1)
        params = {"params": [{"jobs": ["JobHostUnits"],
                              "parent-id": 1,
                              "container-type": "lxd",
                              }],
                  }
        self.assertEqual("Client", self.backend.lastType)
        self.assertEqual("AddMachines", self.backend.lastRequest)
        self.assertEqual(params, self.backend.lastParams)
        self.backend.response(
            {u'machines': [{u'Error': None, u'machine': u'1'}]})
        self.assertEqual("1", self.successResultOf(deferred))
