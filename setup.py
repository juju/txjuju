import os
from importlib import import_module
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


basedir = os.path.abspath(os.path.dirname(__file__) or '.')
README = os.path.join(basedir, 'README.md')

# required data

package_name = 'txjuju'
NAME = package_name
SUMMARY = 'A twisted-based Juju client.'
AUTHOR = 'Canonical Landscape team'
EMAIL = 'juju@lists.ubuntu.com'
PROJECT_URL = 'https://github.com/juju/txjuju'
LICENSE = 'LGPLv3'

DESCRIPTION = ''
if os.path.exists(README):
    with open(README) as readme_file:
        DESCRIPTION = readme_file.read()

# dymanically generated data

VERSION = import_module(package_name).__version__

# set up packages

exclude_dirs = [
        'tests',
        ]

PACKAGES = []
for path, dirs, files in os.walk(package_name):
    if "__init__.py" not in files:
        continue
    path = path.split(os.sep)
    if path[-1] in exclude_dirs:
        continue
    PACKAGES.append(".".join(path))

# dependencies

DEPS = [
        'twisted',
        'yaml',
        ]
TESTING_DEPS = [
        'fixtures',
        'testtools',
        ]


if __name__ == "__main__":
    setup(name=NAME,
          version=VERSION,
          author=AUTHOR,
          author_email=EMAIL,
          url=PROJECT_URL,
          license=LICENSE,
          description=SUMMARY,
          long_description=DESCRIPTION,
          packages=PACKAGES,

          # for distutils
          requires=DEPS,

          # for setuptools
          install_requires=DEPS,
          )
