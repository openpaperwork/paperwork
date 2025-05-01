import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core

from paperwork_backend.interfaces.docs import DocOpener

from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector
from paperwork_gtk.interfaces.doc_selection import DocSelection
from paperwork_gtk.interfaces.doc_viewer import PageViewerListener
from paperwork_gtk.interfaces.exporter import GtkExporter


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_export_many"


class Plugin(
    openpaperwork_core.PluginBase,
    AppAction,
    Chkdeps,
    DocOpener,
    PageViewerListener,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': AppActionCollector,
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': DocSelection,
                'defaults': ['paperwork_gtk.doc_selection'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.active_doc = (None, None)
        self.active_page_idx = 0
        if not GLIB_AVAILABLE:
            return
        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._export)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    @openpaperwork_core.noop
    def doc_close(self):
        pass

    def on_page_shown(self, active_page_idx):
        self.active_page_idx = active_page_idx

    def _export(self, action, parameter):
        docs = set()
        self.core.call_all(DocSelection.doc_selection_get, docs)
        self.core.call_all(
            GtkExporter.gtk_open_exporter_multiple_docs, docs,
            self.active_doc[0], self.active_doc[1], self.active_page_idx
        )

    @openpaperwork_core.noop
    def on_page_size_obtained(self, page):
        pass
