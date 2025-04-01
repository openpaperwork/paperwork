import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'action',
            'action_app',
            'action_app_open_settings',
            'chkdeps',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'gtk_settings_dialog',
                'defaults': ['paperwork_gtk.settings'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        if not GLIB_AVAILABLE:
            return
        action = Gio.SimpleAction.new('open_settings', None)
        action.connect("activate", self._open_settings)
        self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _open_settings(self, *args, **kwargs):
        self.core.call_success("gtk_open_settings")
