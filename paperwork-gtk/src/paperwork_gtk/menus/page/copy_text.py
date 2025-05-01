import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core
import openpaperwork_core.deps

from paperwork_gtk import _
from paperwork_gtk.interfaces.doc_viewer import PageMenu
from paperwork_gtk.interfaces.doc_viewer import PageMenuListener


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "page_copy_text"


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    PageMenuListener,
):
    PRIORITY = 1000

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': PageMenu,
                'defaults': [
                    'paperwork_gtk.mainwindow.docview.pageinfo.actions'
                ],
            },
        ]

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def on_page_menu_ready(self):
        item = Gio.MenuItem.new(
            _("Copy selected text"), "win." + ACTION_NAME
        )
        self.core.call_all(PageMenu.page_menu_append_item, item)
