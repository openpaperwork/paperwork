"""
Workaround for the fact that "import pkg_resources" never works when frozen
with Msys2 + cx_freeze ...
"""

import logging
import os
import pathlib
import sys

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class FakePathCtxManager:
    def __init__(self, file_path):
        self.file_path = file_path

    def __enter__(self):
        return self.file_path

    def __exit__(self, type, value, traceback):
        pass


class Plugin(PluginBase):
    PRIORITY = 100

    def get_interfaces(self):
        return ['resources']

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python'],
            },
        ]

    def resources_get_file(self, pkg, filename):
        if not getattr(sys, 'frozen', False):
            return None

        # cx_freeze: pkg_resources doesn't work (can't import it), so we keep
        # the data files beside the executable.
        path = os.path.join(
            os.path.dirname(sys.executable),
            "data",
            pkg.replace(".", os.path.sep),
            filename
        )
        if not os.path.exists(path):
            LOGGER.warning(
                "Failed to find %s/%s (tried %s)",
                pkg, filename, path
            )
            return None
        return FakePathCtxManager(pathlib.Path(path).resolve())

    def resources_get_dir(self, pkg, dirname):
        return self.resources_get_file(pkg, dirname)
