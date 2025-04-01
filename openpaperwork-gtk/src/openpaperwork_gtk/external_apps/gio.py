import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except ImportError:
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 75

    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'external_apps',
        ]

    @classmethod
    def get_deps(cls):
        return []

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'] = openpaperwork_core.deps.GLIB

    def external_app_open_file(self, file_url):
        LOGGER.info("Opening file '%s' using Gio", file_url)
        if not Gio.AppInfo.launch_default_for_uri(file_url):
            LOGGER.warning("Failed to opening file '%s' using Gio", file_url)
            return None
        return True

    def external_app_open_folder(self, folder_url):
        return self.external_app_open_file(folder_url)
