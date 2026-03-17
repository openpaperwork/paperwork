import logging

from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.pages import PageManagement

from paperwork_gtk.interfaces.search_field import SearchField

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core
import openpaperwork_core.deps

from openpaperwork_gtk.interfaces.dialogs import GtkYesNoDialog
from openpaperwork_gtk.interfaces.dialogs import GtkYesNoDialogListener

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.docs import DocOpener

from paperwork_gtk import _
from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector
from paperwork_gtk.interfaces.doc_viewer import PageViewerListener


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "page_delete"


class Plugin(
    openpaperwork_core.PluginBase,
    AppAction,
    Chkdeps,
    DocOpener,
    GtkYesNoDialogListener,
    PageViewerListener,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=AppActionCollector,
                defaults=['paperwork_gtk.mainwindow.window'],
            ),
            openpaperwork_core.Dependency(
                interface=DocStorage,
                defaults=['paperwork_backend.model.workdir'],
            ),
            openpaperwork_core.Dependency(
                interface=DocTransactionManager,
                defaults=['paperwork_backend.sync'],
            ),
            openpaperwork_core.Dependency(
                interface=GtkYesNoDialog,
                defaults=['openpaperwork_gtk.dialogs.yes_no'],
            ),
            openpaperwork_core.Dependency(
                interface=PageManagement,
                defaults=["paperwork_backend.interfaces.pages"],
            ),
            openpaperwork_core.Dependency(
                interface=SearchField,
                defaults=[],
                optional=True,
            ),
        ]

    def __init__(self, core):
        super().__init__(core)

        self.active_doc = None
        self.active_page_idx = -1

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
        self.active_doc = None

    def on_page_shown(self, page_idx):
        self.active_page_idx = page_idx

    def _delete(self, *args, **kwargs):
        assert self.active_doc is not None

        LOGGER.info(
            "Asking confirmation before deleting page %d of document %s",
            self.active_page_idx, self.active_doc[0]
        )
        msg = (
            _(
                "Are you sure you want to delete page"
                " {page_idx} of document {doc_id} ?"
            ).format(
                page_idx=(self.active_page_idx + 1),
                doc_id=self.active_doc[0]
            )
        )
        self.core.call_success(
            GtkYesNoDialog.gtk_show_dialog_yes_no, self, msg, self.active_doc
        )

    def on_dialog_yes_no_reply(
            self, parent, reply, *args, **kwargs):
        if parent is not self:
            return
        if not reply:
            return

        (active_doc,) = args
        (doc_id, doc_url) = active_doc
        page_idx = self.active_page_idx

        LOGGER.info("Will delete page %s p%d", doc_id, page_idx)

        self.core.call_all(PageManagement.page_delete_by_url, doc_url, page_idx)
        self.core.call_all(SearchField.search_update_document_list)
        self.core.call_all(DocOpener.doc_reload)

        self.core.call_success(DocTransactionManager.transaction_simple, [('upd', doc_id),])

    @openpaperwork_core.noop
    def on_page_size_obtained(self, page):
        pass
