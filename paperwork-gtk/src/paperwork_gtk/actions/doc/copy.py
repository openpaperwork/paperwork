import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_copy"


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.active_doc = (None, None)

    def get_interfaces(self):
        return [
            'action',
            'action_doc',
            'action_doc_copy',
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
        action.connect("activate", self._copy)
        self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def doc_close(self):
        self.active_doc = (None, None)

    def _copy(self, action, parameter):
        assert self.active_doc is not None
        (src_doc_id, src_doc_url) = self.active_doc

        LOGGER.info("Will copy doc %s", src_doc_id)
        dst_doc_url = self.core.call_success("doc_copy_by_url", src_doc_url)
        dst_doc_id = self.core.call_success("doc_url_to_id", dst_doc_url)
        LOGGER.info("New document: %s (copied from %s)", dst_doc_id, src_doc_id)

        self.core.call_all("doc_open", dst_doc_id, dst_doc_url)
        self.core.call_all("search_update_document_list")
        self.core.call_success("transaction_simple", [('add', dst_doc_id),])
