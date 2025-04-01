import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "page_move_to_doc"


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'action',
            'action_page',
            'action_page_move_to_doc',
            'chkdeps',
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
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'gtk_mainwindow',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_search_field',
                'defaults': ['paperwork_gtk.mainwindow.search.field'],
            },
            {
                'interface': 'pages',
                'defaults': [
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.img_overlay',
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.pdf',
                ],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)

        self.active_doc = None
        self.active_page_idx = -1
        self.waiting_for_target_doc = False

        if not GLIB_AVAILABLE:
            return

        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.actions.page.move_to_doc", "move_to_doc.glade"
        )
        if widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return
        widget_tree.get_object("move_to_doc_cancel").connect(
            "clicked", self._cancel_move_to_doc
        )
        self.core.call_all(
            "mainwindow_add",
            "right", "move_to_doc",
            -9999999999,
            widget_tree.get_object("move_to_doc_header"),
            widget_tree.get_object("move_to_doc"),
        )

        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._start_move_to_doc)
        self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        new_active_doc = (doc_id, doc_url)
        if self.waiting_for_target_doc:
            self.waiting_for_target_doc = False
            self._move_to_doc(new_active_doc)
        self.active_doc = new_active_doc

    def doc_close(self):
        self.active_doc = None

    def on_page_shown(self, page_idx):
        self.active_page_idx = page_idx

    def _start_move_to_doc(self, *args, **kwargs):
        assert self.active_doc is not None
        if self.active_page_idx < 0:
            return
        LOGGER.info("Starting 'move to doc' process")
        self.core.call_all("mainwindow_show", "right", "move_to_doc")
        self.core.call_all("mainwindow_show", "left", "doclist")
        self.waiting_for_target_doc = True

    def _run_transaction(self, original_doc, target_doc):
        nb_remaining_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", original_doc[1]
        )
        if nb_remaining_pages is None:
            nb_remaining_pages = 0

        self.core.call_success(
            "transaction_simple_promise",
            [
                ('upd', target_doc[0]),
                (
                    'upd' if nb_remaining_pages > 0 else 'del',
                    original_doc[0]
                ),
            ]
        )

    def _move_to_doc(self, target_doc):
        promise = openpaperwork_core.promise.Promise(self.core)
        promise = promise.then(
            self.core.call_all,
            "page_move_by_url",
            self.active_doc[1], self.active_page_idx,
            target_doc[1], 0
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self.core.call_one,
            "mainloop_schedule", self.core.call_all,
            "doc_reload", *self.active_doc
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self.core.call_one,
            "mainloop_schedule", self.core.call_all,
            "doc_reload", *target_doc
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self.core.call_all,
            "search_update_document_list"
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self._run_transaction, self.active_doc, target_doc
        )

        self.core.call_success("transaction_schedule", promise)

    def _cancel_move_to_doc(self, *args, **kwargs):
        LOGGER.info("Canceling 'move to doc' process")
        self.core.call_all("mainwindow_back", "right")
        self.waiting_for_target_doc = False
