import itertools
import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_change_labels"


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'action',
            'action_docs',
            'action_docs_properties',
            'chkdeps',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'doc_labels',
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                'interface': 'doc_selection',
                'defaults': ['paperwork_gtk.doc_selection'],
            },
            {
                'interface': 'gtk_doc_properties',
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
        self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _open_editor(self, action, parameter):
        selection = set()
        self.core.call_all("doc_selection_get", selection)

        if len(selection) <= 0:
            LOGGER.info("No document selected")
            return

        LOGGER.info("Opening properties for %d documents", len(selection))
        self.core.call_all("open_docs_properties", selection)
