import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps

from ... import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -10000

    @classmethod
    def get_interfaces(cls):
        return [
            'menu',
            'menu_app',
            'menu_app_about',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'action_app_open_about',
                'defaults': ['paperwork_gtk.actions.app.open_about'],
            },
            {
                'interface': 'gtk_app_menu',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def on_doclist_initialized(self):
        item = Gio.MenuItem.new(_("About"), "win.open_about")
        self.core.call_all("menu_app_append_item", item)
