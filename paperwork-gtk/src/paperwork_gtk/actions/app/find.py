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
from paperwork_gtk.interfaces.search_field import SearchField


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    AppAction,
    Chkdeps,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=AppActionCollector,
                defaults=['paperwork_gtk.mainwindow.window'],
            ),
            openpaperwork_core.Dependency(
                interface=SearchField,
                defaults=['paperwork_gtk.mainwindow.search.field'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        if not GIO_AVAILABLE:
            return
        action = Gio.SimpleAction.new('app_find', None)
        action.connect("activate", self._focus_on_search_field)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GIO_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _focus_on_search_field(self, action, parameter):
        self.core.call_all(SearchField.search_focus)
