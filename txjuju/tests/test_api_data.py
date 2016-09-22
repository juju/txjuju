# Copyright 2016 Canonical Limited.  All rights reserved.

from unittest import TestCase

from txjuju.api_data import (
    JujuApplicationConfig, MachineInfo, AnnotationInfo, ActionInfo)


class JujuApplicationConfigTest(TestCase):

    def test_has_options(self):
        """
        JujuApplicationConfig.has_options() returns whether the
        config has the given options.
        """
        config = JujuApplicationConfig("nfs", "nfs", config={
            u"foo": {u"default": True,
                     u"description": u"Foo.",
                     u"type": u"string",
                     u"value": u"bar"}})
        self.assertTrue(config.has_options(["foo"]))
        self.assertFalse(config.has_options(["bar"]))

    def test_get_value(self):
        """
        JujuApplicationConfig.get_value() returns the value of an option.
        """
        config = JujuApplicationConfig("nfs", "nfs", config={
            u"foo": {u"default": True,
                     u"description": u"Foo.",
                     u"type": u"string",
                     u"value": u"bar"}})
        self.assertEqual("bar", config.get_value("foo"))


class AnnotationInfoTest(TestCase):

    def test_constructor(self):
        """
        The L{AnnotationInfo} constructor parses the given tag identifier,
        extracting the entity kind and ID.
        """
        info = AnnotationInfo("unit-mysql-0", {})
        self.assertEqual("unit", info.entityKind)
        self.assertEqual("mysql/0", info.entityId)

    def test_constructor_with_dashed_service_name(self):
        """
        The L{AnnotationInfo} constructor can handle dashes in the service
        name, they won't be replaced with slashes.
        """
        info = AnnotationInfo("unit-landscape-client-0", {})
        self.assertEqual("unit", info.entityKind)
        self.assertEqual("landscape-client/0", info.entityId)


class MachineInfoTest(TestCase):

    def test_defaults(self):
        """A MachineInfo can be created with default values."""
        info = MachineInfo("1")
        self.assertEqual("1", info.id)
        self.assertEqual("", info.instanceId)
        self.assertEqual("pending", info.status)
        self.assertEqual("", info.statusInfo)
        self.assertEqual([], info.jobs)
        self.assertIsNone(info.address)
        self.assertIsNone(info.hasVote)
        self.assertIsNone(info.wantsVote)

    def test_status_info(self):
        "The statusInfo field can be set when creating a MachineInfo."""
        info = MachineInfo("1", statusInfo="some info")
        self.assertEqual("some info", info.statusInfo)

    def test_is_state_server_false(self):
        """
        MachineInfo.is_state_server is False if the machine doesn't have
        the "JobManageEnviron" job.
        """
        info = MachineInfo("1", jobs=["JobHostUnits"])
        self.assertFalse(info.is_state_server)

    def test_is_state_server_true_juju1(self):
        """
        Machine.is_state_server is True if the machine has the
        "JobManageEnviron" job.
        """
        info = MachineInfo("1", jobs=["JobManageEnviron", "JobHostUnits"])
        self.assertTrue(info.is_state_server)

    def test_is_state_server_true_juju2(self):
        """
        Machine.is_state_server is True if the machine has the
        "JobManageModel" job.
        """
        info = MachineInfo("1", jobs=["JobManageModel", "JobHostUnits"])
        self.assertTrue(info.is_state_server)

    def test_no_ha_flags(self):
        """
        If HA flags are not passed as parameters, they're set to None.
        """
        info = MachineInfo("1")
        self.assertIsNone(info.hasVote)
        self.assertIsNone(info.wantsVote)

    def test_ha_flags(self):
        """
        If HA flags are passed as parameters, they're set in the MachineInfo.
        """
        info = MachineInfo("1", hasVote=False, wantsVote=True)
        self.assertFalse(info.hasVote)
        self.assertTrue(info.wantsVote)


class AcitonInfoTest(TestCase):

    def test_defaults(self):
        """An ActionInfo can be created with default values."""
        info = ActionInfo("1-2-3", "an-action", "service/3", "pending")
        self.assertEqual("1-2-3", info.id)
        self.assertEqual("an-action", info.name)
        self.assertEqual("service/3", info.receiver)
        self.assertEqual("pending", info.status)
        self.assertEqual("", info.message)
        self.assertEqual({}, info.results)

    def test_message(self):
        """A message can be set in the ActionInfo."""
        info = ActionInfo(
            "1-2-3", "an-action", "service/3", "pending", message="a message")
        self.assertEqual("a message", info.message)

    def test_results(self):
        """Results can be set in the ActionInfo."""
        info = ActionInfo(
            "1-2-3", "an-action", "service/3", "pending",
            results={"foo": "bar"})
        self.assertEqual({"foo": "bar"}, info.results)
