# Copyright 2016 Canonical Limited.  All rights reserved.

import unittest
from zipfile import ZipFile

import yaml

from txjuju.charm import CharmInMemory, Metadata


class CharmInMemoryTest(unittest.TestCase):

    def test_open_as_zip_file(self):
        meta = Metadata("spam", "uh", "uh-huh")
        ch = CharmInMemory(meta)
        archive = ch.open_as_zip_file()
        zf = ZipFile(archive, "r")
        filenames = zf.namelist()
        data = {}
        for filename in filenames:
            data[filename] = zf.open(filename).read()

        self.assertEqual(filenames, ["metadata.yaml"])
        self.assertEqual(yaml.load(data["metadata.yaml"]), {
            "name": "spam",
            "summary": "uh",
            "description": "uh-huh",
            "subordinate": False,
            })


class MetadataTest(unittest.TestCase):

    def test_as_yamlable(self):
        meta = Metadata("spam", "uh", "uh-huh")
        content = meta.as_yamlable()

        self.assertEqual(content, {
            "name": "spam",
            "summary": "uh",
            "description": "uh-huh",
            "subordinate": False,
            })
