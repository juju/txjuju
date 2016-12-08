# Copyright 2016 Canonical Limited.  All rights reserved.

from collections import namedtuple
from StringIO import StringIO
from zipfile import ZipFile

import yaml


class Charm(object):
    """A single charm."""
    # See github.com/juju/charm/charm.go.

    def meta(self):
        """Return the charm's metadata."""
        raise NotImplementedError

    def config(self):
        """Return the charm's config."""
        raise NotImplementedError

    def metrics(self):
        """Return the charm's metrics."""
        raise NotImplementedError

    def actions(self):
        """Return the charm's actions."""
        raise NotImplementedError

    def revision(self):
        """Return the charm's revision."""
        raise NotImplementedError

    def open_as_zip_file(self):
        """Return a file-like object containing the zipped charm dir."""
        raise NotImplementedError


class CharmInMemory(object):
    """A single charm with all its data stored in memory."""

    def __init__(self, metadata):
        self._metadata = metadata

    def open_as_zip_file(self):
        """Return a file-like object containing the zipped charm dir."""
        archive = StringIO()
        zf = ZipFile(archive, "w")

        content = self._metadata.as_yamlable()
        data = yaml.dump(content, default_flow_style=False)
        zf.writestr(self._metadata.FILENAME, data)

        zf.close()
        archive.seek(0)
        return archive


class Metadata(
        namedtuple("Metadata",
                   ("name summary description is_subordinate"
                    ))):
    """A charm's metadata."""
    # See github.com/juju/charm/meta.go.

    #name
    #summary
    #description
    #is_subordinate  # bool
    #provides  # {name: Relation}
    #requires  # {name: Relation}
    #peers  # {name: Relation}
    #extra_bindings
    #categories  # [str]
    #tags  # [str]
    #series  # [str]
    #storage
    #payloads
    #resources
    #terms  # [str]
    #min_juju_version  # x.y.z

    FILENAME = "metadata.yaml"

    def __new__(cls, name, summary, description, is_subordinate=False,
                **kwargs):
        return super(Metadata, cls).__new__(
            cls, name, summary, description, is_subordinate, **kwargs)

    def as_yamlable(self):
        return {"name": self.name,
                "summary": self.summary,
                "description": self.description,
                "subordinate": self.is_subordinate,
                }
