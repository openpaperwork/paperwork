import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.mainloop import Mainloop
import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise

from openpaperwork_gtk.interfaces.gtk import GtkResources

from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.docs import (
    DocOpener,
    Docs
)
from paperwork_backend.interfaces.pages import (
    PageImg,
    PageManagement
)

from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector
from paperwork_gtk.interfaces.doc_list import DocList
from paperwork_gtk.interfaces.doc_viewer import PageViewerListener
from paperwork_gtk.interfaces.main_window import MainWindow
from paperwork_gtk.interfaces.search_field import SearchField


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "page_move_to_doc"


class Plugin(
    openpaperwork_core.PluginBase,
    AppAction,
    Chkdeps,
    DocOpener,
    PageViewerListener,
):
    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            {
                'interface': AppActionCollector,
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': DocList,
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                "interface": Docs,
                "defaults": ["paperwork_backend.model"],
            },
            {
                'interface': DocTransactionManager,
                'defaults': ['paperwork_backend.sync'],
            },
            {
                'interface': GtkResources,
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                "interface": Mainloop,
                "defaults": ["openpaperwork_gtk.mainloop.glib"],
            },
            {
                'interface': MainWindow,
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': PageImg,
                'defaults': [
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.img_overlay',
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.pdf',
                ],
            },
            {
                'interface': SearchField,
                'defaults': ['paperwork_gtk.mainwindow.search.field'],
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
            GtkResources.gtk_load_widget_tree,
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
            MainWindow.mainwindow_add,
            "right", "move_to_doc",
            -9999999999,
            widget_tree.get_object("move_to_doc_header"),
            widget_tree.get_object("move_to_doc"),
        )

        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._start_move_to_doc)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        new_active_doc = (doc_id, doc_url)
        if self.waiting_for_target_doc:
            self.waiting_for_target_doc = False
            self._move_to_doc(new_active_doc)
        self.active_doc = new_active_doc

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    def doc_close(self):
        self.active_doc = None

    def on_page_shown(self, page_idx):
        self.active_page_idx = page_idx

    def _start_move_to_doc(self, *args, **kwargs):
        assert self.active_doc is not None
        if self.active_page_idx < 0:
            return
        LOGGER.info("Starting 'move to doc' process")
        self.core.call_all(MainWindow.mainwindow_show, "right", "move_to_doc")
        self.core.call_all(MainWindow.mainwindow_show, "left", "doclist")
        self.waiting_for_target_doc = True

    def _run_transaction(self, original_doc, target_doc):
        nb_remaining_pages = self.core.call_success(
            Docs.doc_get_nb_pages_by_url, original_doc[1]
        )
        if nb_remaining_pages is None:
            nb_remaining_pages = 0

        self.core.call_success(
            DocTransactionManager.transaction_simple_promise,
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
            PageManagement.page_move_by_url,
            self.active_doc[1], self.active_page_idx,
            target_doc[1], 0
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self.core.call_one,
            Mainloop.mainloop_schedule, self.core.call_all,
            DocOpener.doc_reload, *self.active_doc
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self.core.call_one,
            Mainloop.mainloop_schedule, self.core.call_all,
            DocOpener.doc_reload, *target_doc
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

        self.core.call_success(DocTransactionManager.transaction_schedule, promise)

    def _cancel_move_to_doc(self, *args, **kwargs):
        LOGGER.info("Canceling 'move to doc' process")
        self.core.call_all(MainWindow.mainwindow_back, "right")
        self.waiting_for_target_doc = False

    @openpaperwork_core.noop
    def on_page_size_obtained(self, page):
        pass
