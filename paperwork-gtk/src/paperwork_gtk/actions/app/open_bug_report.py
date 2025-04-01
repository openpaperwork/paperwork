import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'action',
            'action_app',
            'action_app_open_bug_report',
            'chkdeps',
            'gtk_window_listener',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)

        self.active_doc = None

        if not GLIB_AVAILABLE:
            return

        action = Gio.SimpleAction.new('open_bug_report', None)
        action.connect("activate", self._open_bug_report)
        self.core.call_all("app_actions_add", action)

    def _open_bug_report(self, *args, **kwargs):
        self.core.call_all("open_bug_report")
