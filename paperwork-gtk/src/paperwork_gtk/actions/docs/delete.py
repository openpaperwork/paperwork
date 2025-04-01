import gc
import logging
import os

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_delete_many"


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'action',
            'action_docs',
            'action_docs_delete',
            'chkdeps',
            'doc_action',
            'doc_open',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'doc_selection',
                'defaults': ['paperwork_gtk.doc_selection'],
            },
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_dialog_yes_no',
                'defaults': ['openpaperwork_gtk.dialogs.yes_no'],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        if not GLIB_AVAILABLE:
            return
        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._delete)
        self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _delete(self, action, parameter):
        docs = set()
        self.core.call_all("doc_selection_get", docs)
        LOGGER.info("Asking confirmation before deleting %d doc", len(docs))
        msg = _('Are you sure you want to delete %d documents ?') % len(docs)

        if os.name == "nt":
            # On Windows, we have to be absolutely sure the PDF is actually
            # closed when we try to delete it because Windows s*cks pony d*cks
            # in h*ll.
            self.core.call_all("doc_close")
            # there is no "close()" method in Poppler
            gc.collect()

        self.core.call_all("gtk_show_dialog_yes_no", self, msg, docs)

    def on_dialog_yes_no_reply(self, parent, reply, *args, **kwargs):
        if parent is not self:
            return
        if not reply:
            return
        (docs,) = args

        self.core.call_all("doc_close")

        for (doc_id, doc_url) in docs:
            LOGGER.info("Deleting document %s", doc_id)
            self.core.call_all("storage_delete_doc_id", doc_id)

        self.core.call_all("search_update_document_list")

        self.core.call_success(
            "transaction_simple", [
                ('del', doc_id) for (doc_id, doc_url) in docs
            ]
        )
