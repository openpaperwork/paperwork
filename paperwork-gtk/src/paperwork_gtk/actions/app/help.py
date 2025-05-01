import logging

try:
    from gi.repository import Gio
    GIO_AVAILABLE = True
except (ImportError, ValueError):
    GIO_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps

import openpaperwork_core
import openpaperwork_core.deps

from paperwork_backend.interfaces.docs import DocOpener

from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector
from paperwork_gtk.interfaces.help import HelpDocs


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
                "interface": DocOpener,
                "defaults": [],
                "optional": True,
            },
            {
                'interface': HelpDocs,
                'defaults': ['paperwork_gtk.model.help'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        if not GIO_AVAILABLE:
            return
        for (title, file_name) in self.core.call_success(HelpDocs.help_get_files):
            action = Gio.SimpleAction.new('open_help.' + file_name, None)
            action.connect("activate", self._doc_open_help, file_name)
            self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GIO_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _doc_open_help(self, action, parameter, file_name):
        doc_url = self.core.call_success(HelpDocs.help_get_file, file_name)
        self.core.call_all(DocOpener.doc_open, "help_" + file_name, doc_url)
