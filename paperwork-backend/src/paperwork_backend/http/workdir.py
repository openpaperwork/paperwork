from typing import Optional
import logging

import openpaperwork_core
import openpaperwork_core.util


LOGGER = logging.getLogger(__name__)

PATH_PREFIX = "/papers/"


class Plugin(
        openpaperwork_core.PluginBase,
        metaclass=openpaperwork_core.util.Singleton):
    PRIORITY = -100

    def __init__(self):
        super().__init__()
        self.workdir = None

    def get_interfaces(self):
        return [
            "https_workdir_extension",
        ]

    def get_deps(self):
        return [
            {
                "interface": "config",
                "defaults": ["openpaperwork_core.config"],
            },
            {
                "interface": "document_storage",
                "defaults": ["paperwork_backend.model.workdir"],
            },
            {
                "interface": "fs",
                "defaults": ["openpaperwork_core.fs.python"],
            },
        ]

    def init(self, core):
        super().init(core)
        self._reload_workdir()
        self.core.call_all("config_add_observer", "workdir", self._reload_workdir)

    def _reload_workdir(self):
        self.workdir = self.core.call_success("config_get", "workdir")

    def _get_real_path(self, verb, query_path):
        if not query_path.startswith(PATH_PREFIX):
            return (None, None, None)

        path = query_path.lstrip(PATH_PREFIX)
        path = self.workdir + "/" + path
        path = self.core.call_success("fs_resolve", path)
        if not path.startswith(self.workdir):
            return (None, None, None)
        exists = self.core.call_success("fs_exists", path)
        if not exists:
            LOGGER.error("%s %s (-> %s): doesn't exist", verb, query_path, path)
            return (None, None, None)
        is_dir = self.core.call_success("fs_isdir", path)
        if is_dir:
            LOGGER.error("%s %s (-> %s): directory", verb, query_path, path)
            return (None, None, None)
        size = self.core.call_success("fs_getsize", path)
        mtime = self.core.call_success("fs_get_mtime", path)
        return (path, size, mtime)

    def http_backend_head(self, query_path: str) -> Optional[bytes]:
        (path, size, mtime) = self._get_real_path("HEAD", query_path)
        if path is None:
            return None
        return (mtime, size)

    def http_backend_get(self, query_path: str) -> Optional[bytes]:
        (path, size, mtime) = self._get_real_path("GET", query_path)
        if path is None:
            return None
        with self.core.call_success("fs_open", path, "rb") as fd:
            return (mtime, fd.read())
