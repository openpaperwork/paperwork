import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.promise

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_redo_ocr_many"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -50

    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'menu',
            'menu_docs',
            'menu_docs_redo_ocr',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'action_docs_redo_ocr',
                'defaults': ['paperwork_gtk.actions.docs.redo_ocr'],
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

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def on_doclist_initialized(self):
        item = Gio.MenuItem.new(_("Redo OCR"), "win." + ACTION_NAME)
        self.core.call_all("docs_menu_append_item", item)
