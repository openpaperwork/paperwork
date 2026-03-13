import json
import logging

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.resources import Resources
import openpaperwork_core

from paperwork_backend.interfaces.authors import Authors


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Authors,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=['openpaperwork_gtk.fs.gio'],
            ),
            openpaperwork_core.Dependency(
                interface=Resources,
                defaults=['openpaperwork_core.resources.setuptools'],
            ),
        ]

    def authors_get(self, out: dict):
        file_path_ctx = self.core.call_success(
            Resources.resources_get_file, "paperwork_backend.authors",
            "AUTHORS.json"
        )
        if file_path_ctx is None:
            LOGGER.error("AUTHORS.json is missing !")
            return None
        with file_path_ctx as file_path:
            file_path = self.core.call_success(Fs.fs_safe, file_path)
            with self.core.call_success(Fs.fs_open, file_path, 'r') as fd:
                content = fd.read()
        content = json.loads(content)

        for category in content:
            for (category_name, authors) in category.items():
                out[category_name] = authors

        return True
