import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "page_delete"


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.active_doc = None
        self.active_page_idx = -1

    def get_interfaces(self):
        return [
            'action',
            'action_page',
            'action_page_delete',
            'chkdeps',
            'doc_open',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
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

    def init(self, core):
        super().init(core)
        if not GLIB_AVAILABLE:
            return

        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._delete)
        self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

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
            "gtk_show_dialog_yes_no", self, msg, self.active_doc
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

        self.core.call_all("page_delete_by_url", doc_url, page_idx)
        self.core.call_all("search_update_document_list")
        self.core.call_all("doc_reload", doc_id, doc_url)

        self.core.call_success("transaction_simple", [('upd', doc_id),])
