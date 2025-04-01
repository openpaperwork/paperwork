import logging

try:
    from gi.repository import Gio
    GIO_AVAILABLE = True
except (ImportError, ValueError):
    GIO_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'action',
            'action_doc',
            'action_doc_prev_next',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        if not GIO_AVAILABLE:
            return
        action = Gio.SimpleAction.new('doc_prev', None)
        action.connect("activate", self._goto, -1)
        self.core.call_all("app_actions_add", action)
        action = Gio.SimpleAction.new('doc_next', None)
        action.connect("activate", self._goto, 1)
        self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GIO_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _goto(self, action, parameter, offset):
        self.core.call_all("open_next_doc", offset)
