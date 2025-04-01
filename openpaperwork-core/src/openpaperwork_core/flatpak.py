import logging
import os
import shutil
import tempfile

from . import PluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    PRIORITY = 75

    @classmethod
    def get_interfaces(cls):
        return [
            'flatpak',
            'stats',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'data_versioning',
                'defaults': ['openpaperwork_core.data_versioning'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python'],
            },
            {
                'interface': 'paths',
                'defaults': ['openpaperwork_core.paths.xdg'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.tmp_files = set()
        self.flatpak = (os.name == 'posix') and bool(self.core.call_success(
            "fs_isdir", "file:///app"
        ))
        LOGGER.info("Flatpak environment: %s", self.flatpak)
        self.tmp_dir = self.core.call_success(
            "fs_join",
            self.core.call_success("paths_get_data_dir"), "tmp"
        )

    def is_in_flatpak(self):
        if self.flatpak:
            return True
        return None

    def fs_mktemp(self, prefix=None, suffix=None, mode='w+b', **kwargs):
        """
        Modifies slightly the behaviour of fs_mktemp():

        When making a bug report, we use temporary files. We need the user
        to be able to access those temporary files with external applications.

        With Flatpak, the easiest way for that is to place the temporary files
        somewhere in the user home directory.
        """
        if not self.flatpak:
            return None

        self.core.call_success("fs_mkdir_p", self.tmp_dir)
        tmp = tempfile.NamedTemporaryFile(
            prefix=prefix, suffix=suffix, delete=False, mode=mode,
            dir=self.core.call_success("fs_unsafe", self.tmp_dir)
        )
        LOGGER.info("Flatpak tmp file: %s --> %s", self.tmp_dir, tmp.name)
        self.tmp_files.add(tmp.name)
        return (self.core.call_success("fs_safe", tmp.name), tmp)

    def on_quit(self):
        if not self.flatpak:
            return
        if self.core.call_success("fs_exists", self.tmp_dir) is not None:
            shutil.rmtree(self.core.call_success("fs_unsafe", self.tmp_dir))

    def stats_get(self, out: dict):
        if not self.flatpak:
            return

        if 'os_name' in out:
            out['os_name'] += ' (flatpak)'
        else:
            out['os_name'] = 'GNU/Linux (flatpak)'
