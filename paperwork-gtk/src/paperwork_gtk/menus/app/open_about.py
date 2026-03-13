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
from paperwork_gtk.interfaces.app_menu import AppMenu
from paperwork_gtk.interfaces.doc_list import DocListListener


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    DocListListener,
):
    PRIORITY = -10000

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=AppMenu,
                defaults=['paperwork_gtk.mainwindow.doclist'],
            ),
        ]

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def on_doclist_initialized(self):
        item = Gio.MenuItem.new(_("About"), "win.open_about")
        self.core.call_all(AppMenu.menu_app_append_item, item)

    @openpaperwork_core.noop
    def on_doc_list_clear(self):
        pass

    @openpaperwork_core.noop
    def on_doc_box_creation(self, doc_id, row, flowlayout):
        pass

    @openpaperwork_core.noop
    def on_doc_list_visibility_changed(self):
        pass

    @openpaperwork_core.noop
    def on_doc_box_visible(self, doc_id, gtk_row, layout):
        pass
