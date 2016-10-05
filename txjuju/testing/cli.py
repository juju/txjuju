# Copyright 2016 Canonical Limited.  All rights reserved.

from twisted.internet.defer import succeed

from txjuju.errors import CLIError


class StubCLI(object):

    def __init__(self, juju_home, fail=False):
        self._fail = fail
        self.called_fetch = False
        self.called_juju_status = False
        self.called_get_all_logs = False
        self.calls = []

    def fetch_file(self, *args, **kwargs):
        self.called_fetch = True
        self.calls.append(("fetch_file", args, kwargs))
        if self._fail:
            raise CLIError("Fetch failed", "ERROR: Fetch failed", code=1)
        return succeed("Success from FakeJujuProcess.fetch_file")

    def get_juju_status(self, *args, **kwargs):
        self.called_juju_status = True
        self.calls.append(("get_juju_status", args, kwargs))
        if self._fail:
            raise CLIError("Status failed", "ERROR: Status failed", code=1)
        return succeed("Success from FakeJujuProcess.get_juju_status")

    def get_all_logs(self, *args, **kwargs):
        self.called_get_all_logs = True
        self.calls.append(("get_all_logs", args, kwargs))
        if self._fail:
            raise CLIError("Logs failed", "ERROR: Logs failed", code=1)
        return succeed("Success from FakeJujuProcess.get_all_logs")
