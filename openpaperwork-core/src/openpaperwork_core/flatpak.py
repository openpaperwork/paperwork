import logging
import os
import shutil
import tempfile

from openpaperwork_core.interfaces.flatpak import Flatpak
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.paths import Paths
from openpaperwork_core.interfaces.quit import QuitListener
from openpaperwork_core.interfaces.stats import Stats
import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Flatpak,
    Fs,
    QuitListener,
    Stats,
):
    PRIORITY = 75

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Paths,
                defaults=['openpaperwork_core.paths.xdg'],
                optional=True,  # to break dependency loops
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.tmp_files = set()
        self.flatpak = None
        self.tmp_dir = None

    def _lazy_init(self):
        if self.flatpak is not None:
            return
        self.flatpak = (os.name == 'posix') and bool(self.core.call_success(
            Fs.fs_isdir, "file:///app"
        ))
        LOGGER.info("Flatpak environment: %s", self.flatpak)
        self.tmp_dir = self.core.call_success(
            Fs.fs_join,
            self.core.call_success(Paths.paths_get_data_dir), "tmp"
        )

    def is_in_flatpak(self):
        self._lazy_init()
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
        self._lazy_init()
        if not self.flatpak:
            return None

        self.core.call_success(Fs.fs_mkdir_p, self.tmp_dir)
        tmp = tempfile.NamedTemporaryFile(
            prefix=prefix, suffix=suffix, delete=False, mode=mode,
            dir=self.core.call_success(Fs.fs_unsafe, self.tmp_dir)
        )
        LOGGER.info("Flatpak tmp file: %s --> %s", self.tmp_dir, tmp.name)
        self.tmp_files.add(tmp.name)
        return (self.core.call_success(Fs.fs_safe, tmp.name), tmp)

    def on_quit(self):
        self._lazy_init()
        if not self.flatpak:
            return
        if self.core.call_success(Fs.fs_exists, self.tmp_dir) is not None:
            shutil.rmtree(self.core.call_success(Fs.fs_unsafe, self.tmp_dir))

    def stats_get(self, out: dict):
        self._lazy_init()
        if not self.flatpak:
            return

        if 'os_name' in out:
            out['os_name'] += ' (flatpak)'
        else:
            out['os_name'] = 'GNU/Linux (flatpak)'

    @openpaperwork_core.noop
    def fs_safe(self, uri):
        pass

    @openpaperwork_core.noop
    def fs_unsafe(self, uri):
        pass

    @openpaperwork_core.noop
    def fs_join(self, base, url):
        pass

    @openpaperwork_core.noop
    def fs_basename(self, url):
        pass

    @openpaperwork_core.noop
    def fs_dirname(self, url):
        pass

    @openpaperwork_core.noop
    def fs_hash(self, url):
        pass

    @openpaperwork_core.noop
    def fs_open(self, uri, mode='r', **kwargs):
        pass

    @openpaperwork_core.noop
    def fs_exists(self, uri):
        pass

    @openpaperwork_core.noop
    def fs_listdir(self, uri):
        pass

    @openpaperwork_core.noop
    def fs_rename(self, old_uri, new_uri):
        pass

    @openpaperwork_core.noop
    def fs_unlink(self, uri, **kwargs):
        pass

    @openpaperwork_core.noop
    def fs_rm_rf(self, uri, **kwargs):
        pass

    @openpaperwork_core.noop
    def fs_get_mtime(self, uri):
        pass

    @openpaperwork_core.noop
    def fs_getsize(self, uri):
        pass

    @openpaperwork_core.noop
    def fs_isdir(self, uri):
        pass

    @openpaperwork_core.noop
    def fs_copy(self, old_uri, new_uri):
        pass

    @openpaperwork_core.noop
    def fs_copytree(self, old_uri, new_uri):
        pass

    @openpaperwork_core.noop
    def fs_mkdir_p(self, uri):
        pass

    @openpaperwork_core.noop
    def fs_recurse(self, parent_uri, dir_included=False):
        pass

    @openpaperwork_core.noop
    def fs_hide(self, uri):
        pass

    @openpaperwork_core.noop
    def fs_get_mime(self, uri):
        pass

    @openpaperwork_core.noop
    def fs_iswritable(self, uri):
        pass

    @openpaperwork_core.noop
    def fs_resolve(self, uri):
        pass
