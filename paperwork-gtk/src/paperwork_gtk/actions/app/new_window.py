import logging

try:
    from gi.repository import Gio
    GIO_AVAILABLE = True
except (ImportError, ValueError):
    GIO_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps

import paperwork_backend
import paperwork_gtk.main


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'action',
            'action_app',
            'action_app_new_window',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        if not GIO_AVAILABLE:
            return
        action = Gio.SimpleAction.new('new_window', None)
        action.connect("activate", self._make_new_window)
        self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GIO_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _make_new_window(self, *args, **kwargs):
        core = openpaperwork_core.Core()
        for module_name in paperwork_gtk.main.REQUIRED_PLUGINS:
            core.load(module_name)
        for module_name in paperwork_backend.DEFAULT_CONFIG_PLUGINS:
            core.load(module_name)

        core.init()
        core.call_all("config_load")
        core.call_all(
            "config_load_plugins", "paperwork-gtk",
            paperwork_gtk.main.DEFAULT_GUI_PLUGINS
        )
        core.call_all("on_gtk_initialized")
