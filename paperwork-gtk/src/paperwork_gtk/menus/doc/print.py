import logging

import openpaperwork_core

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_print"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -10

    @classmethod
    def get_interfaces(cls):
        return [
            'menu',
            'menu_doc',
            'menu_doc_print',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'doc_actions',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.active_doc = None
        self.active_windows = []

    def on_doclist_initialized(self):
        self.core.call_all(
            "add_doc_action", _("Print document"), "win." + ACTION_NAME
        )
