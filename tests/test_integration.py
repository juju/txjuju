# Copyright 2016 Canonical Limited.  All rights reserved.

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from txjuju.api import Endpoint, JujuAPIClient
from txjuju.errors import APIAuthError, APIRequestError

from testresources import ResourcedTestCase

from testtools import TestCase
from testtools.twistedsupport import AsynchronousDeferredRunTest

from fakejuju.fixture import MODEL_UUID

from tests.resources import fakejuju


class JujuAPIClientIntegrationTest(TestCase, ResourcedTestCase):

    resources = [("fakejuju", fakejuju)]

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=60)

    @inlineCallbacks
    def setUp(self):
        super(JujuAPIClientIntegrationTest, self).setUp()
        cli = self.fakejuju.cli()
        cli.execute("bootstrap", "foo", "bar")
        self.addCleanup(cli.execute, "destroy-controller", "-y", "bar")

        addr = "localhost:%d" % (self.fakejuju.port - 1)
        self.endpoint = Endpoint(reactor, addr, JujuAPIClient, uuid=MODEL_UUID)
        self.client = yield self.endpoint.connect()

    def tearDown(self):
        deferred = self.client.close()
        super(JujuAPIClientIntegrationTest, self).tearDown()
        return deferred

    @inlineCallbacks
    def test_api_info(self):
        """
        The login() method returns an APIInfo object with information about
        the server.
        """
        api_info = yield self.client.login("user-admin", "dummy-secret")
        self.assertEqual([self.endpoint.addr], api_info.endpoints)

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
    def test_run_on_all_machines(self):
        """
        The runOnAllMachines() method runs the given command on all available
        machines.
        """
        yield self.client.login("user-admin", "dummy-secret")
        [actionId] = yield self.client.runOnAllMachines("/bin/true")

        watcher = yield self.client.watchAll()
        completed = False
        while not completed:
            deltas = yield self.client.allWatcherNext(watcher)
            for delta in deltas:
                if delta.kind == "action":
                    action = delta.info
                    if action.status == "completed":
                        completed = True
                        break

        self.assertEqual(actionId, action.id)

    @inlineCallbacks
    def test_add_machine(self):
        """
        The addMachine() method adds a new machine to the model.
        """
        yield self.client.login("user-admin", "dummy-secret")
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
        yield self.client.login("user-admin", "dummy-secret")
        machineId = yield self.client.addMachine(
            scope=MODEL_UUID, directive="reber.scapestack")
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
        yield self.client.login("user-admin", "dummy-secret")
        machineId = yield self.client.addMachine(parentId="0")
        self.assertEqual("0/lxd/0", machineId)
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
        yield self.client.login("user-admin", "dummy-secret")
        yield self.client.addCharm("cs:xenial/ubuntu-10")
        yield self.client.serviceDeploy("ubuntu", "cs:xenial/ubuntu-10")
        watcher = yield self.client.watchAll()
        service = None
        while service is None:
            deltas = yield self.client.allWatcherNext(watcher)
            for delta in deltas:
                if delta.kind == "application":
                    service = delta.info
                    break
        self.assertEqual("ubuntu", service.name)
        self.assertEqual("cs:xenial/ubuntu-10", service.charmURL)

    @inlineCallbacks
    def test_add_unit(self):
        """
        The addUnit() method adds a new unit with the specified placement.
        """
        yield self.client.login("user-admin", "dummy-secret")
        yield self.client.addCharm("cs:xenial/ubuntu-10")
        yield self.client.serviceDeploy("ubuntu", "cs:xenial/ubuntu-10")
        yield self.client.addMachine()
        watcher = yield self.client.watchAll()
        unitName = yield self.client.addUnit(
            "ubuntu", scope="lxd", directive="1")
        self.assertEqual("ubuntu/0", unitName)
        started = False
        while not started:
            deltas = yield self.client.allWatcherNext(watcher)
            for delta in deltas:
                if delta.kind == "unit":
                    unit = delta.info
                    if unit.workload_status.current == "active":
                        started = True
                        break
        self.assertEqual("ubuntu/0", unit.name)

    @inlineCallbacks
    def test_enqueueAction(self):
        """
        The enqueueAction() methods enqueues an a action against the
        specified receiver.
        """
        yield self.client.login("user-admin", "dummy-secret")
        yield self.client.addCharm("cs:xenial/postgresql-114")
        yield self.client.serviceDeploy(
            "postgresql", "cs:xenial/postgresql-114")
        yield self.client.addUnit("postgresql", scope=None, directive="0")
        watcher = yield self.client.watchAll()
        while True:
            deltas = yield self.client.allWatcherNext(watcher)
            for delta in deltas:
                if delta.kind == "unit":
                    if delta.info.workload_status.current == "active":
                        break
            else:
                continue
            break
        yield self.client.enqueueAction("replication-pause", "postgresql/0")

        completed = False
        while not completed:
            deltas = yield self.client.allWatcherNext(watcher)
            for delta in deltas:
                if delta.kind == "action":
                    action = delta.info
                    if action.status == "completed":
                        completed = True
                        break

        self.assertEqual("postgresql/0", action.receiver)

    @inlineCallbacks
    def test_enqueueUnknownAction(self):
        """
        Enqueueing an unknown action results in an error.
        """
        yield self.client.login("user-admin", "dummy-secret")
        yield self.client.addCharm("cs:xenial/ubuntu-10")
        yield self.client.serviceDeploy("ubuntu", "cs:xenial/ubuntu-10")
        yield self.client.addUnit("ubuntu", scope=None, directive="0")
        watcher = yield self.client.watchAll()
        while True:
            deltas = yield self.client.allWatcherNext(watcher)
            for delta in deltas:
                if delta.kind == "unit":
                    if delta.info.workload_status.current == "active":
                        break
            else:
                continue
            break
        try:
            yield self.client.enqueueAction("do-something", "ubuntu/0")
        except APIRequestError as exception:
            self.assertEqual(
                "no actions defined on charm \"cs:xenial/ubuntu-10\"",
                exception.error)
            self.assertEqual("", exception.code)
        else:
            self.fail("Expected request error")
