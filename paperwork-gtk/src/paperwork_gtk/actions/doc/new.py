import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps

import openpaperwork_core
import openpaperwork_core.deps

from paperwork_backend.interfaces.docs import NewDocOpener

from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    AppAction,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=AppActionCollector,
                defaults=['paperwork_gtk.mainwindow.window'],
            ),
            openpaperwork_core.Dependency(
                interface=NewDocOpener,
                defaults=['paperwork_gtk.mainwindow.doclist'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        if not GLIB_AVAILABLE:
            return

        action = Gio.SimpleAction.new("doc_new", None)
        action.connect("activate", self._open_new_doc)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _open_new_doc(self, *args, **kwargs):
        self.core.call_all(NewDocOpener.doc_open_new)
