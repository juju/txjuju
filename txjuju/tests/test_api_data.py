# Copyright 2016 Canonical Limited.  All rights reserved.

from unittest import TestCase

from txjuju.api_data import (
    APIInfo, ModelInfo, CloudInfo, WatcherDelta, StatusInfo,
    MachineInfo, ApplicationInfo, UnitInfo, ActionInfo, AnnotationInfo,
    ApplicationConfig, RunResult)


class APIInfoTest(TestCase):

    def test___repr__(self):
        """APIInfo has a useful repr."""
        info = APIInfo(["localhost:12345"], "some-uuid")
        result = repr(info)

        self.assertEqual(
            result,
            "APIInfo(endpoints=['localhost:12345'], uuid='some-uuid')")


class StatusInfoTest(TestCase):

    def test_all_args(self):
        """StatusInfo.__init__() works when provided all arguments."""
        info = StatusInfo("active", "a-ok")

        self.assertEqual(info.current, "active")
        self.assertEqual(info.message, "a-ok")

    def test_current_None(self):
        """StatusInfo.__init__() allows current to be None."""
        info = StatusInfo(None)

        self.assertIs(info.current, None)

    def test_all_defaults(self):
        """StatusInfo.__init__() has some default arguments."""
        info = StatusInfo("active")

        self.assertEqual(info.current, "active")
        self.assertEqual(info.message, "")

    def test_missing_required(self):
        """StatusInfo.__init__() has some required arguments."""
        with self.assertRaises(TypeError):
            StatusInfo()

    def test___repr__(self):
        """StatusInfo has a useful repr."""
        info = StatusInfo("active", "a-ok")
        result = repr(info)

        self.assertEqual(
            result, "StatusInfo(current='active', message='a-ok')")


class ModelInfoTest(TestCase):

    def test___repr___full(self):
        """ModelInfo has a useful repr when initialized with all args."""
        info = ModelInfo(
            "my-model", "dummy", "trusty", "some-uuid", "other-uuid",
            "cloud-my-cloud", "some-region", "credential-my-auth")
        result = repr(info)

        self.assertEqual(
            result,
            ("ModelInfo(name='my-model', providerType='dummy',"
             " defaultSeries='trusty', uuid='some-uuid',"
             " controllerUUID='other-uuid', cloudTag='cloud-my-cloud',"
             " cloudRegion='some-region',"
             " cloudCredentialTag='credential-my-auth')"))

    def test___repr___minimal(self):
        """ModelInfo has a useful repr when initialized with minimal args."""
        info = ModelInfo("my-model", "dummy", "trusty", "some-uuid")
        result = repr(info)

        self.assertEqual(
            result,
            ("ModelInfo(name='my-model', providerType='dummy',"
             " defaultSeries='trusty', uuid='some-uuid', controllerUUID=None,"
             " cloudTag=None, cloudRegion=None, cloudCredentialTag=None)"))


class CloudInfoTest(TestCase):

    def test___repr__(self):
        """CloudInfo has a useful repr."""
        info = CloudInfo("dummy", ["x"], "localhost", "localhost", ["y"])
        result = repr(info)

        self.assertEqual(
            result,
            ("CloudInfo(cloudtype='dummy', authTypes=['x'],"
             " endpoint='localhost', storageEndpoint='localhost',"
             " regions=['y'])"))


class ApplicationInfoTest(TestCase):

    def test___repr___full(self):
        """ApplicationInfo has a useful repr when initialized with all args."""
        info = ApplicationInfo(
            "spam", True, "some-url", "dying", "eggs=yes", {"x": "y"})
        result = repr(info)

        self.assertEqual(
            result,
            ("ApplicationInfo(name='spam', exposed=True, charmURL='some-url',"
             " life='dying', constraints='eggs=yes', config={'x': 'y'})"))

    def test___repr___minimal(self):
        """ApplicationInfo has a useful repr when initialized
        with minimal args."""
        info = ApplicationInfo("spam")
        result = repr(info)

        self.assertEqual(
            result,
            ("ApplicationInfo(name='spam', exposed=False, charmURL=None,"
             " life=None, constraints=None, config=None)"))


class UnitInfoTest(TestCase):

    def test___repr___full(self):
        """UnitInfo has a useful repr when initialized with all args."""
        info = UnitInfo(
            "spam/1", "spam", "trusty", "some-url", "localhost", "localhost",
            "1", ["80"], "alive", "some info")
        result = repr(info)

        self.assertEqual(
            result,
            ("UnitInfo(name='spam/1', applicationName='spam',"
             " series='trusty', charmURL='some-url',"
             " publicAddress='localhost', privateAddress='localhost',"
             " machineId='1', ports=['80'], status='alive',"
             " statusInfo='some info')"))

    def test___repr___minimal(self):
        """UnitInfo has a useful repr when initialized with minimal args."""
        info = UnitInfo("spam/1", "spam")
        result = repr(info)

        self.assertEqual(
            result,
            ("UnitInfo(name='spam/1', applicationName='spam', series=None,"
             " charmURL=None, publicAddress=None, privateAddress=None,"
             " machineId=u'', ports=(), status=None, statusInfo=u'')"))


class ApplicationConfigTest(TestCase):

    def test___repr___full(self):
        """ApplicationConfig has a useful repr when initialized
        with all args."""
        cfg = ApplicationConfig("nfs", "nfs", "spam=yes", {"eggs": 42})
        result = repr(cfg)

        self.assertEqual(
            result,
            ("ApplicationConfig(application='nfs', charm='nfs',"
             " constraints='spam=yes', config={'eggs': 42})"))

    def test___repr___minimal(self):
        """ApplicationConfig has a useful repr when initialized
        with minimal args."""
        cfg = ApplicationConfig("nfs", "nfs")
        result = repr(cfg)

        self.assertEqual(
            result,
            ("ApplicationConfig(application='nfs', charm='nfs',"
             " constraints=None, config={})"))

    def test_has_options(self):
        """
        ApplicationConfig.has_options() returns whether the
        config has the given options.
        """
        config = ApplicationConfig("nfs", "nfs", config={
            u"foo": {u"default": True,
                     u"description": u"Foo.",
                     u"type": u"string",
                     u"value": u"bar"}})
        self.assertTrue(config.has_options(["foo"]))
        self.assertFalse(config.has_options(["bar"]))

    def test_get_value(self):
        """
        ApplicationConfig.get_value() returns the value of an option.
        """
        config = ApplicationConfig("nfs", "nfs", config={
            u"foo": {u"default": True,
                     u"description": u"Foo.",
                     u"type": u"string",
                     u"value": u"bar"}})
        self.assertEqual("bar", config.get_value("foo"))


class AnnotationInfoTest(TestCase):

    def test___repr__(self):
        """APIInfo has a useful repr."""
        info = AnnotationInfo("machine-0", {"x": "y"})
        result = repr(info)

        self.assertEqual(
            result,
            "AnnotationInfo(tag='machine-0', pairs={'x': 'y'})")

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

    def test___repr___full(self):
        """MachineInfo has a useful repr when initialized with all args."""
        info = MachineInfo(
            "1", "inst1", "alive", "some info", ["JobHostUnits"],
            "localhost", False, True)
        result = repr(info)

        self.assertEqual(
            result,
            ("MachineInfo(id='1', instanceId='inst1', status='alive',"
             " statusInfo='some info', jobs=['JobHostUnits'],"
             " address='localhost', hasVote=False, wantsVote=True)"))

    def test___repr___minimal(self):
        """MachineInfo has a useful repr when initialized with minimal args."""
        info = MachineInfo("1")
        result = repr(info)

        self.assertEqual(
            result,
            ("MachineInfo(id='1', instanceId=u'', status=u'pending',"
             " statusInfo=u'', jobs=[], address=None,"
             " hasVote=None, wantsVote=None)"))

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


class ActionInfoTest(TestCase):

    def test___repr___full(self):
        """ActionInfo has a useful repr when initialized with all args."""
        info = ActionInfo(
            "some-id", "an-action", "my-svc/3", "pending", "some msg",
            {"x": "y"})
        result = repr(info)

        self.assertEqual(
            result,
            ("ActionInfo(id='some-id', name='an-action', receiver='my-svc/3',"
             " status='pending', message='some msg', results={'x': 'y'})"))

    def test___repr___minimal(self):
        """ActionInfo has a useful repr when initialized with minimal args."""
        info = ActionInfo("some-id", "an-action", "my-svc/3", "pending")
        result = repr(info)

        self.assertEqual(
            result,
            ("ActionInfo(id='some-id', name='an-action', receiver='my-svc/3',"
             " status='pending', message='', results={})"))

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


class WatcherDeltaTest(TestCase):

    def test___repr__(self):
        """WatcherDelta has a useful repr."""
        delta = WatcherDelta("machine", "change", MachineInfo("1"))
        result = repr(delta)

        self.assertEqual(
            result,
            ("WatcherDelta(kind='machine', verb='change',"
             " info=MachineInfo(id='1', instanceId=u'', status=u'pending',"
             " statusInfo=u'', jobs=[], address=None, hasVote=None,"
             " wantsVote=None))"))


class RunResultTest(TestCase):

    def test___repr__(self):
        """RunResult has a useful repr."""
        runresult = RunResult("xxx", "yyy", 1, "an error")
        result = repr(runresult)

        self.assertEqual(
            result,
            "RunResult(stdout='xxx', stderr='yyy', code=1, error='an error')")
