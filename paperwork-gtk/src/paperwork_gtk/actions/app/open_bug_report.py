import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core

from openpaperwork_gtk.interfaces.bug_report import GtkBugReportDisplay

from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
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
                interface=GtkBugReportDisplay,
                defaults=["openpaperwork_gtk.bug_report"],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)

        self.active_doc = None

        if not GLIB_AVAILABLE:
            return

        action = Gio.SimpleAction.new('open_bug_report', None)
        action.connect("activate", self._open_bug_report)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def _open_bug_report(self, *args, **kwargs):
        self.core.call_all(GtkBugReportDisplay.open_bug_report)
