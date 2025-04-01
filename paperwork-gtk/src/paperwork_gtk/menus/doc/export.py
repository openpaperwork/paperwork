import logging

import openpaperwork_core

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_export"


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'menu',
            'menu_doc',
            'menu_doc_export',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'actions_doc_export',
                'defaults': ['paperwork_gtk.actions.doc.export'],
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
            "add_doc_action", _("Export document"), "win." + ACTION_NAME
        )
