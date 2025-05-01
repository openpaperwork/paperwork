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
from paperwork_gtk.interfaces.doc_selection import DocSelection
from paperwork_gtk.interfaces.search_field import SearchResultsListener


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_select_all"


class Plugin(
    openpaperwork_core.PluginBase,
    AppAction,
    Chkdeps,
    SearchResultsListener,
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
        self.visible_docs = []
        if not GLIB_AVAILABLE:
            return
        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._select_all)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    @openpaperwork_core.noop
    def on_search_start(self, query):
        pass

    def on_search_results(self, query, docs):
        self.visible_docs = docs

    def _select_all(self, action, parameter):
        for doc in self.visible_docs:
            self.core.call_all(DocSelection.doc_selection_add, *doc)
