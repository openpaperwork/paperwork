import logging

import openpaperwork_core

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_redo_ocr"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -90

    @classmethod
    def get_interfaces(cls):
        return [
            'menu',
            'menu_doc',
            'menu_doc_redo_ocr',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'action_doc_redo_ocr',
                'defaults': ['paperwork_gtk.actions.doc.redo_ocr'],
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
            "add_doc_action", _("Redo OCR on document"), "win." + ACTION_NAME
        )
