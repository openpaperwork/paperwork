import gc
import logging
import os

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core
import openpaperwork_core.deps

from openpaperwork_gtk.interfaces.dialogs import (
    GtkYesNoDialog,
    GtkYesNoDialogListener
)

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.docs import DocOpener

from paperwork_gtk import _
from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector
from paperwork_gtk.interfaces.doc_selection import DocSelection
from paperwork_gtk.interfaces.search_field import Search


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_delete_many"


class Plugin(
    openpaperwork_core.PluginBase,
    AppAction,
    Chkdeps,
    GtkYesNoDialogListener,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=AppActionCollector,
                defaults=['paperwork_gtk.mainwindow.window'],
            ),
            openpaperwork_core.Dependency(
                interface=DocOpener,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=DocSelection,
                defaults=['paperwork_gtk.doc_selection'],
            ),
            openpaperwork_core.Dependency(
                interface=DocStorage,
                defaults=['paperwork_backend.model.workdir'],
            ),
            openpaperwork_core.Dependency(
                interface=GtkYesNoDialog,
                defaults=['openpaperwork_gtk.dialogs.yes_no'],
            ),
            openpaperwork_core.Dependency(
                interface=DocTransactionManager,
                defaults=['paperwork_backend.sync'],
            ),
            openpaperwork_core.Dependency(
                interface=Search,
                defaults=[],
                optional=True,
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        if not GLIB_AVAILABLE:
            return
        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._delete)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _delete(self, action, parameter):
        docs = set()
        self.core.call_all(DocSelection.doc_selection_get, docs)
        LOGGER.info("Asking confirmation before deleting %d doc", len(docs))
        msg = _('Are you sure you want to delete %d documents ?') % len(docs)

        if os.name == "nt":
            # On Windows, we have to be absolutely sure the PDF is actually
            # closed when we try to delete it because Windows s*cks pony d*cks
            # in h*ll.
            self.core.call_all(DocOpener.doc_close)
            # there is no "close()" method in Poppler
            gc.collect()

        self.core.call_all(GtkYesNoDialog.gtk_show_dialog_yes_no, self, msg, docs)

    def on_dialog_yes_no_reply(self, parent, reply, *args, **kwargs):
        if parent is not self:
            return
        if not reply:
            return
        (docs,) = args

        self.core.call_all(DocOpener.doc_close)

        for (doc_id, doc_url) in docs:
            LOGGER.info("Deleting document %s", doc_id)
            self.core.call_all(DocStorage.storage_delete_doc_id, doc_id)

        self.core.call_all(Search.search_update_document_list)

        self.core.call_success(
            DocTransactionManager.transaction_simple, [
                ('del', doc_id) for (doc_id, doc_url) in docs
            ]
        )
