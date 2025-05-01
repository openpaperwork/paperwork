import itertools
import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core
import openpaperwork_core.deps

from paperwork_backend.interfaces.doc_labels import DocLabels

from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector
from paperwork_gtk.interfaces.doc_properties import DocProperties
from paperwork_gtk.interfaces.doc_selection import DocSelection


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_change_labels"


class Plugin(
    openpaperwork_core.PluginBase,
    AppAction,
    Chkdeps,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': AppActionCollector,
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': DocLabels,
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                'interface': DocSelection,
                'defaults': ['paperwork_gtk.doc_selection'],
            },
            {
                'interface': DocProperties,
                'defaults': ['paperwork_gtk.mainwindow.docproperties'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.menu_add = None
        self.menu_remove = None
        self.idx_generator = itertools.count()
        if not GLIB_AVAILABLE:
            return
        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._open_editor)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _open_editor(self, action, parameter):
        selection = set()
        self.core.call_all(DocSelection.doc_selection_get, selection)

        if len(selection) <= 0:
            LOGGER.info("No document selected")
            return

        LOGGER.info("Opening properties for %d documents", len(selection))
        self.core.call_all(DocProperties.open_docs_properties, selection)
