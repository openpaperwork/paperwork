import logging

try:
    from gi.repository import Gio
    GIO_AVAILABLE = True
except (ImportError, ValueError):
    GIO_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core
import openpaperwork_core.deps

from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector
from paperwork_gtk.interfaces.doc_list import DocList


LOGGER = logging.getLogger(__name__)


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
                'interface': DocList,
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        if not GIO_AVAILABLE:
            return
        action = Gio.SimpleAction.new('doc_prev', None)
        action.connect("activate", self._goto, -1)
        self.core.call_all(AppActionCollector.app_actions_add, action)
        action = Gio.SimpleAction.new('doc_next', None)
        action.connect("activate", self._goto, 1)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GIO_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _goto(self, action, parameter, offset):
        self.core.call_all(DocList.open_next_doc, offset)
