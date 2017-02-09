# Copyright 2016 Canonical Limited.  All rights reserved.
import os

from testresources import OptimisingTestSuite


def load_tests(loader, standard_tests, pattern):
    this_dir = os.path.dirname(__file__)
    package_tests = loader.discover(start_dir=this_dir, pattern=pattern)
    standard_tests.addTests(package_tests)
    return OptimisingTestSuite(standard_tests)
