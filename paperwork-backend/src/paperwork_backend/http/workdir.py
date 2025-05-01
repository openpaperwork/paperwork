from typing import Optional
import logging

from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.fs import Fs
import openpaperwork_core
import openpaperwork_core.util

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.http import HttpBackendExtension
import paperwork_backend.http


LOGGER = logging.getLogger(__name__)

PATH_PREFIX = "/papers/"


class Plugin(
    openpaperwork_core.PluginBase,
    HttpBackendExtension,
    metaclass=openpaperwork_core.util.Singleton
):
    PRIORITY = -100

    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": Config,
                "defaults": ["openpaperwork_core.config"],
            },
            {
                "interface": DocStorage,
                "defaults": ["paperwork_backend.model.workdir"],
            },
            {
                "interface": Fs,
                "defaults": ["openpaperwork_core.fs.python"],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.workdir = None
        self._reload_workdir()
        self.core.call_all(Config.config_add_observer, "workdir", self._reload_workdir)

    def _reload_workdir(self):
        self.workdir = self.core.call_success(Config.config_get, "workdir")

    def _get_real_path(self, verb, query_path):
        if not query_path.startswith(PATH_PREFIX):
            return None

        path = query_path.lstrip(PATH_PREFIX)
        path = self.workdir + "/" + path
        path = self.core.call_success(Fs.fs_resolve, path)
        if not path.startswith(self.workdir):
            return None
        exists = self.core.call_success(Fs.fs_exists, path)
        if not exists:
            LOGGER.error("%s %s (-> %s): doesn't exist", verb, query_path, path)
            return None
        is_dir = self.core.call_success(Fs.fs_isdir, path)
        if is_dir:
            LOGGER.error("%s %s (-> %s): directory", verb, query_path, path)
            return None
        return path

    def http_backend_head(self, request) -> Optional[paperwork_backend.http.BackendReply]:
        return self.http_backend_get(request)

    def http_backend_get(self, request) -> Optional[paperwork_backend.http.BackendReply]:
        path = self._get_real_path("GET", request.path)
        if path is None:
            return None
        return paperwork_backend.http.BackendReply(
            http_code=200,
            content_length=self.core.call_success(Fs.fs_getsize, path),
            last_modified=self.core.call_success(Fs.fs_get_mtime, path),
            content_fd=self.core.call_success(Fs.fs_open, path, "rb"),
            etag=self.core.call_success(Fs.fs_hash, path),
        )
