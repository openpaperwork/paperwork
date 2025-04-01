import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_select_all"


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'action',
            'action_docs',
            'action_docs_select_all',
            'chkdeps',
            'search_listener',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'doc_selection',
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
        self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def on_search_results(self, query, docs):
        self.visible_docs = docs

    def _select_all(self, action, parameter):
        for doc in self.visible_docs:
            self.core.call_all("doc_selection_add", *doc)
