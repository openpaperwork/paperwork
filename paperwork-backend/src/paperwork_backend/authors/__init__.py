import json
import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['authors']

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'resources',
                'defaults': ['openpaperwork_core.resources.setuptools'],
            },
        ]

    def authors_get(self, out: dict):
        file_path_ctx = self.core.call_success(
            "resources_get_file", "paperwork_backend.authors",
            "AUTHORS.json"
        )
        if file_path_ctx is None:
            LOGGER.error("AUTHORS.json is missing !")
            return None
        with file_path_ctx as file_path:
            file_path = self.core.call_success("fs_safe", file_path)
            with self.core.call_success("fs_open", file_path, 'r') as fd:
                content = fd.read()
        content = json.loads(content)

        for category in content:
            for (category_name, authors) in category.items():
                out[category_name] = authors

        return True
