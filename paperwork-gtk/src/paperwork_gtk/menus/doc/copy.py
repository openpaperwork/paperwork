import logging

import openpaperwork_core

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_copy"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -25

    @classmethod
    def get_interfaces(cls):
        return [
            'menu',
            'menu_doc',
            'menu_doc_copy',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'action_doc_copy',
                'defaults': ['paperwork_gtk.actions.doc.copy'],
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
            "add_doc_action", _("Duplicate document"), "win." + ACTION_NAME
        )
