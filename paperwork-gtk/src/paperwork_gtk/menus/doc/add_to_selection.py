import logging

import openpaperwork_core
import openpaperwork_core.deps

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_add_to_selection"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000

    @classmethod
    def get_interfaces(cls):
        return [
            'menu',
            'menu_doc',
            'menu_doc_add_to_selection',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'action_doc_add_to_selection',
                'defaults': ['paperwork_gtk.actions.doc.add_to_selection'],
            },
            {
                'interface': 'doc_actions',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
        ]

    def on_doclist_initialized(self):
        self.core.call_all(
            "add_doc_action", _("Add to selection"), "win." + ACTION_NAME
        )
