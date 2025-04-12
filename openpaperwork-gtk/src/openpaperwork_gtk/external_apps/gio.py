import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except ImportError:
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.external_apps import ExternalApps
import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    ExternalApps,
):
    PRIORITY = 75

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

    @openpaperwork_core.noop
    def external_app_can_send_as_attachment(self) -> None:
        pass

    @openpaperwork_core.noop
    def external_app_send_as_attachment(self, uri) -> None:
        pass
