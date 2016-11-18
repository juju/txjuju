# Copyright 2016 Canonical Limited.  All rights reserved.

"""Constants and helpers for Juju entity state.

See https://godoc.org/github.com/juju/juju/status.
"""

# common to agents
ERROR = "error"

# machine agents
PENDING = "pending"
STARTED = "started"
STOPPED = "stopped"
DOWN = "down"

# unit agents
ALLOCATING = "allocating"
REBOOTING = "rebooting"
EXECUTING = "executing"  # running hook or action
IDLE = "idle"  # started
FAILED = "failed"
LOST = "lost"

# unit workloads and applications
MAINTENANCE = "maintenance"
TERMINATED = "terminated"  # machine
UNKNOWN = "unknown"
WAITING = "waiting"
BLOCKED = "failed"
ACTIVE = "active"  # i.e. started

# instances
EMPTY = ""
PROVISIONING = "allocating"
RUNNING = "running"
PROVISIONING_ERROR = "provisioning error"
