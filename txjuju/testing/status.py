# Copyright 2016 Canonical Limited.  All rights reserved.

from txjuju import status
from txjuju.api_data import StatusInfo


###########################################################
# The following are dummy status info that may be used
# in tests.  Note that ERROR and the middle 4 workload
# statuses have user-supplied messages.  All the others
# match what Juju produces during normal operation.

ERROR = StatusInfo(status.ERROR, "an error occurred")

# machine-agent-only
PENDING = StatusInfo(status.PENDING, "")
# See github.com/juju/juju/worker/provisioner/provisioner_task.go.
PENDING_RETRY = StatusInfo(
    status.PENDING, "will retry to start instance in 10s")
STARTED = StatusInfo(status.STARTED, "")
STOPPED = StatusInfo(status.STOPPED, "")
DOWN = StatusInfo(status.DOWN, "")

# unit-agent-only
ALLOCATING = StatusInfo(status.ALLOCATING, "waiting for machine")
REBOOTING = StatusInfo(status.REBOOTING, "")
EXECUTING = StatusInfo(status.EXECUTING, "running commands")
EXECUTING_HOOK = StatusInfo(status.EXECUTING, "running install hook")
EXECUTING_ACTION = StatusInfo(status.EXECUTING, "running action \"spam\"")
IDLE = StatusInfo(status.IDLE, "")
FAILED = StatusInfo(status.FAILED, "resolver loop error")
LOST = StatusInfo(status.LOST, "agent is not communicating with the server")

# unit-workload-only
UNKNOWN = StatusInfo(status.UNKNOWN, "installing agent")
ACTIVE = StatusInfo(status.ACTIVE, "I'm active!")
MAINTENANCE = StatusInfo(status.MAINTENANCE, "I'm working on something")
WAITING = StatusInfo(status.WAITING, "I'm waiting for a relation")
BLOCKED = StatusInfo(status.BLOCKED, "I'm blocked on a resource")
TERMINATED = StatusInfo(status.TERMINATED, "")

# See github.com/juju/juju/worker/deployer/deployer.go.
INSTALLING = StatusInfo(status.WAITING, "installing agent")
