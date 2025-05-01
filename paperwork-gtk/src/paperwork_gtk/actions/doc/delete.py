import gc
import logging
import os

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.mainloop import Mainloop
import openpaperwork_core
import openpaperwork_core.deps

from openpaperwork_gtk.interfaces.dialogs import GtkYesNoDialog
from openpaperwork_gtk.interfaces.dialogs import GtkYesNoDialogListener

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.docs import DocOpener

from paperwork_gtk import _
from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector
from paperwork_gtk.interfaces.doc_list import DocSearch


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_delete"


class Plugin(
    openpaperwork_core.PluginBase,
    AppAction,
    Chkdeps,
    DocOpener,
    GtkYesNoDialogListener,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': AppActionCollector,
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                "interface": DocSearch,
                "defaults": [],
                "optional": True,
            },
            {
                'interface': DocStorage,
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': DocTransactionManager,
                'defaults': ['paperwork_backend.sync'],
            },
            {
                'interface': GtkYesNoDialog,
                'defaults': ['openpaperwork_gtk.dialogs.yes_no'],
            },
            {
                "interface": Mainloop,
                "defaults": ["openpaperwork_gtk.mainloop.glib"],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.active_doc = (None, None)
        if not GLIB_AVAILABLE:
            return
        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._delete)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    def doc_close(self):
        self.active_doc = (None, None)

    def _delete(self, action, parameter):
        assert self.active_doc is not None
        active = self.active_doc

        LOGGER.info("Asking confirmation before deleting doc %s", active[0])
        msg = _('Are you sure you want to delete document %s ?') % active[0]

        active_doc = self.active_doc

        if os.name == "nt":
            # On Windows, we have to be absolutely sure the PDF is actually
            # closed when we try to delete it because Windows s*cks pony d*cks
            # in h*ll.
            self.core.call_all(DocOpener.doc_close)
            # there is no "close()" method in Poppler
            gc.collect()

        self.core.call_all(
            GtkYesNoDialog.gtk_show_dialog_yes_no, self, msg, active_doc
        )

    def on_dialog_yes_no_reply(self, parent, reply, *args, **kwargs):
        if parent is not self:
            return
        if not reply:
            return

        (active_doc,) = args
        (doc_id, doc_url) = active_doc

        LOGGER.info("Will delete doc %s", doc_id)

        self.core.call_all(DocOpener.doc_close)
        if os.name == "nt":
            # there is no "close()" method in Poppler
            gc.collect()

        self.core.call_success(
            Mainloop.mainloop_schedule, self._really_delete, doc_id
        )

    def _really_delete(self, doc_id):
        self.core.call_all(DocStorage.storage_delete_doc_id, doc_id)
        self.core.call_all(DocSearch.search_refresh)

        self.core.call_success(DocTransactionManager.transaction_simple, [('del', doc_id),])
