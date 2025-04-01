from typing import Optional
import logging

try:
    from gi.repository import Gio
    GIO_AVAILABLE = True
except (ImportError, ValueError):
    GIO_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps


from ... import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -1000

    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'menu',
            'menu_app',
            'menu_app_help',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'action_app_help',
                'defaults': ['paperwork_gtk.actions.app.help'],
            },
            {
                'interface': 'help_documents',
                'defaults': ['paperwork_gtk.model.help'],
            },
            {
                'interface': 'gtk_app_menu',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.menu: Optional[Gio.Menu] = None
        if not GIO_AVAILABLE:
            return
        self.menu = Gio.Menu()

    def chkdeps(self, out: dict):
        if not GIO_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def on_doclist_initialized(self):
        for (title, file_name) in self.core.call_success("help_get_files"):
            item = Gio.MenuItem.new(title, "win.open_help." + file_name)
            self.menu.append_item(item)
        self.core.call_all("menu_app_append_submenu", _("Help"), self.menu)

    def help_add_menu_item(self, menu_item):
        self.menu.append_item(menu_item)
