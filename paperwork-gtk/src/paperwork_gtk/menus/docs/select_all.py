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
ACTION_NAME = "doc_select_all"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'menu',
            'menu_docs',
            'menu_docs_select_all',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'action_docs_select_all',
                'defaults': ['paperwork_gtk.menus.docs.select_all'],
            },
            {
                'interface': 'docs_actions',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def on_doclist_initialized(self):
        item = Gio.MenuItem.new(_("Select all"), "win." + ACTION_NAME)
        self.core.call_all("docs_menu_append_item", item)
