import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core
import openpaperwork_core.deps

from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector
from paperwork_gtk.interfaces.settings_dialog import SettingsDialog


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    AppAction,
    Chkdeps,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': AppActionCollector,
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': SettingsDialog,
                'defaults': ['paperwork_gtk.settings'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        if not GLIB_AVAILABLE:
            return
        action = Gio.SimpleAction.new('open_settings', None)
        action.connect("activate", self._open_settings)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _open_settings(self, *args, **kwargs):
        self.core.call_success(SettingsDialog.gtk_open_settings)
