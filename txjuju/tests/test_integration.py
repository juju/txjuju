# Copyright 2016 Canonical Limited.  All rights reserved.

from fixtures import TestWithFixtures

from twisted.internet import reactor
from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks

from txjuju.testing import FakeJujuFixture
from txjuju.errors import APIAuthError, APIRequestError
from txjuju.api import Endpoint, Juju1APIClient


class Juju1APIClientIntegrationTest(TestCase, TestWithFixtures):

    @inlineCallbacks
    def setUp(self):
        super(Juju1APIClientIntegrationTest, self).setUp()
        self.juju = self.useFixture(FakeJujuFixture())
        self.endpoint = Endpoint(
            reactor, str(self.juju.address), Juju1APIClient)
        self.client = yield self.endpoint.connect()

    @inlineCallbacks
    def tearDown(self):
        yield self.client.close()
        super(Juju1APIClientIntegrationTest, self).tearDown()

    @inlineCallbacks
    def test_api_info(self):
        """
        The login() method returns an APIInfo object with information about
        the server.
        """
        api_info = yield self.client.login("user-admin", "test")
        self.assertEqual([self.juju.address], api_info.endpoints)

    @inlineCallbacks
    def test_auth_error(self):
        """
        The login() method raises an error if the password is invalid.
        """
        try:
            yield self.client.login("user-admin", "wrong-password")
        except APIAuthError as error:
            self.assertEqual(
                "invalid entity name or password "
                "(code: 'unauthorized access')", str(error))
        else:
            self.fail("Expected authorization error")

    @inlineCallbacks
    def test_model_info(self):
        """
        The modelInfo method returns an ModelInfo object with
        information about the model.
        """
        yield self.client.login("user-admin", "test")
        info = yield self.client.modelInfo(u"some-uuid")
        self.assertEqual("dummyenv", info.name)
        self.assertEqual("dummy", info.providerType)
        self.assertEqual("trusty", info.defaultSeries)
        self.assertEqual(36, len(info.uuid))

    @inlineCallbacks
    def test_run_on_all_machines(self):
        """
        The runOnAllMachines() method runs the given command on all available
        machines.
        """
        yield self.client.login("user-admin", "test")
        result = yield self.client.runOnAllMachines("/bin/true")
        self.assertEqual(["0"], result.keys())
        run_result = result["0"]
        self.assertEqual(0, run_result.code)
        self.assertEqual("", run_result.stdout)
        self.assertEqual("", run_result.stderr)
        self.assertEqual("", run_result.error)

    @inlineCallbacks
    def test_add_machine(self):
        """
        The addMachine() method adds a new machine to the model.
        """
        yield self.client.login("user-admin", "test")
        machineId = yield self.client.addMachine()
        self.assertEqual("1", machineId)
        watcher = yield self.client.watchAll()
        found = False
        while not found:
            deltas = yield self.client.allWatcherNext(watcher)
            for delta in deltas:
                if delta.kind == "machine":
                    machine = delta.info
                    found = (
                        machine.id == machineId and
                        machine.status == "started" and
                        machine.address == "127.0.0.1")
                    if found:
                        break
        self.assertTrue(found)

    @inlineCallbacks
    def test_add_machine_with_placement(self):
        """
        The addMachine() method accepts placement options.
        """
        yield self.client.login("user-admin", "test")
        machineId = yield self.client.addMachine(
            scope=self.juju.uuid, directive="reber.scapestack")
        self.assertEqual("1", machineId)
        watcher = yield self.client.watchAll()
        found = False
        while not found:
            deltas = yield self.client.allWatcherNext(watcher)
            for delta in deltas:
                if delta.kind == "machine":
                    machine = delta.info
                    found = (
                        machine.id == machineId and
                        machine.status == "started" and
                        machine.address == "127.0.0.1")
                    if found:
                        break
        self.assertTrue(found)

    @inlineCallbacks
    def test_add_machine_with_parent_id(self):
        """
        The addMachine() method accepts a parentId option for creating
        containers inside existing machines.
        """
        yield self.client.login("user-admin", "test")
        machineId = yield self.client.addMachine(parentId="0")
        self.assertEqual("0/lxc/0", machineId)
        watcher = yield self.client.watchAll()
        found = False
        while not found:
            deltas = yield self.client.allWatcherNext(watcher)
            for delta in deltas:
                if delta.kind == "machine":
                    machine = delta.info
                    found = (
                        machine.id == machineId and
                        machine.status == "started" and
                        machine.address == "127.0.0.1")
                    if found:
                        break
        self.assertTrue(found)

    @inlineCallbacks
    def test_service_deploy(self):
        """
        The serviceDeploy() method deploys a new service to the model.
        """
        yield self.client.login("user-admin", "test")
        yield self.client.serviceDeploy("ubuntu", "cs:trusty/ubuntu-3")
        watcher = yield self.client.watchAll()
        service = None
        while service is None:
            deltas = yield self.client.allWatcherNext(watcher)
            for delta in deltas:
                if delta.kind == "service":
                    service = delta.info
                    break
        self.assertEqual("ubuntu", service.name)
        self.assertEqual("cs:trusty/ubuntu-3", service.charmURL)

    @inlineCallbacks
    def test_add_unit(self):
        """
        The addUnit() method adds a new unit with the specified placement.
        """
        yield self.client.login("user-admin", "test")
        yield self.client.serviceDeploy("ubuntu", "cs:trusty/ubuntu-3")
        yield self.client.addMachine()
        watcher = yield self.client.watchAll()
        unitName = yield self.client.addUnit(
            "ubuntu", scope="lxc", directive="1")
        self.assertEqual("ubuntu/0", unitName)
        started = False
        while not started:
            deltas = yield self.client.allWatcherNext(watcher)
            for delta in deltas:
                if delta.kind == "unit":
                    unit = delta.info
                    if unit.status == "started":
                        started = True
                        break
        self.assertEqual("ubuntu/0", unit.name)

    @inlineCallbacks
    def test_enqueueAction(self):
        """
        The enqueueAction() methods enqueues an a action against the
        specified receiver.
        """
        yield self.client.login("user-admin", "test")
        yield self.client.serviceDeploy(
            "postgresql", "cs:trusty/postgresql-30")
        yield self.client.addUnit("postgresql", scope=None, directive="0")
        watcher = yield self.client.watchAll()
        while True:
            deltas = yield self.client.allWatcherNext(watcher)
            for delta in deltas:
                if delta.kind == "unit" and delta.info.status == "started":
                    break
            else:
                continue
            break
        yield self.client.enqueueAction("replication-pause", "postgresql/0")
        action = None
        while action is None:
            deltas = yield self.client.allWatcherNext(watcher)
            for delta in deltas:
                if delta.kind == "action":
                    action = delta.info
        self.assertEqual("pending", action.status)
        self.assertEqual("postgresql/0", action.receiver)

    @inlineCallbacks
    def test_enqueueUnknownAction(self):
        """
        Enqueueing an unknown action results in an error.
        """
        yield self.client.login("user-admin", "test")
        yield self.client.serviceDeploy("ubuntu", "cs:trusty/ubuntu-3")
        yield self.client.addUnit("ubuntu", scope=None, directive="0")
        watcher = yield self.client.watchAll()
        while True:
            deltas = yield self.client.allWatcherNext(watcher)
            for delta in deltas:
                if delta.kind == "unit" and delta.info.status == "started":
                    break
            else:
                continue
            break
        try:
            yield self.client.enqueueAction("do-something", "ubuntu/0")
        except APIRequestError as exception:
            self.assertEqual(
                "no actions defined on charm \"cs:trusty/ubuntu-3\"",
                exception.error)
            self.assertEqual("", exception.code)
        else:
            self.fail("Expected request error")
