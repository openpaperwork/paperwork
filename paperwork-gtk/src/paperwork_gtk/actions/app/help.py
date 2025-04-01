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
            'action_app',
            'action_app_help',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'help_documents',
                'defaults': ['paperwork_gtk.model.help'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        if not GIO_AVAILABLE:
            return
        for (title, file_name) in self.core.call_success("help_get_files"):
            action = Gio.SimpleAction.new('open_help.' + file_name, None)
            action.connect("activate", self.doc_open_help, file_name)
            self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GIO_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open_help(self, action, parameter, file_name):
        doc_url = self.core.call_success("help_get_file", file_name)
        self.core.call_all("doc_open", "help_" + file_name, doc_url)
