import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core
import openpaperwork_core.deps

from paperwork_backend.interfaces.docs import DocOpener

from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector
from paperwork_gtk.interfaces.doc_selection import DocSelecter
from paperwork_gtk.interfaces.doc_selection import DocSelection


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_add_to_selection"


class Plugin(
    openpaperwork_core.PluginBase,
    AppAction,
    Chkdeps,
    DocOpener,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': AppActionCollector,
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                "interface": DocSelecter,
                "defaults": ["paperwork_gtk.mainwindow.doclist"],
            },
            {
                'interface': DocSelection,
                'defaults': ['paperwork_gtk.doc_selection'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.active_doc = (None, None)
        self.active_windows = []
        if not GLIB_AVAILABLE:
            return
        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._add_to_selection)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def doc_close(self):
        self.active_doc = (None, None)

    def _add_to_selection(self, action, parameter):
        self.core.call_all(DocSelecter.doc_selection_multiple)
        self.core.call_all(DocSelection.doc_selection_add, *self.active_doc)

    @openpaperwork_core.noop
    def doc_reload(self):
        pass
