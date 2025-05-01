import logging

from paperwork_gtk.interfaces.doc_actions import DocActions

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core
import openpaperwork_core.deps

from paperwork_gtk import _
from paperwork_gtk.interfaces.doc_list import DocListListener


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_select_all"


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    DocListListener,
):
    PRIORITY = 1000

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': DocActions,
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def on_doclist_initialized(self):
        item = Gio.MenuItem.new(_("Select all"), "win." + ACTION_NAME)
        self.core.call_all(DocActions.docs_menu_append_item, item)

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
