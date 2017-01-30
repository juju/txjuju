from testresources import FixtureResource

from fixtures import FakeLogger

from txfixtures import Reactor

from fakejuju.fixture import FakeJuju

# Resource tree
logger = FixtureResource(FakeLogger())
reactor = FixtureResource(Reactor())
fakejuju = FixtureResource(FakeJuju(reactor.fixture))
fakejuju.resources = [("logger", logger), ("reactor", reactor)]
