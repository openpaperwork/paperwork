import logging

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.work_queue import WorkQueue
import openpaperwork_core
import openpaperwork_core.promise

from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.screenshot import Screenshot
from openpaperwork_gtk.interfaces.screenshot import ScreenshotProvider

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_transactions import DocTransactionFactory
from paperwork_backend.interfaces.index import Index
from paperwork_backend.interfaces.sync import Syncable
import paperwork_backend.sync

from paperwork_gtk.interfaces.advanced_search import AdvancedSearchDialog
from paperwork_gtk.interfaces.doc_list import DocList
from paperwork_gtk.interfaces.search_field import Search, SearchResultsListener
from paperwork_gtk.interfaces.search_field import SearchField


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    DocTransactionFactory,
    Search,
    SearchField,
    ScreenshotProvider,
    Syncable,
):
    PRIORITY = -1000000

    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            openpaperwork_core.Dependency(
                interface=AdvancedSearchDialog,
                defaults=["paperwork_gtk.mainwindow.search.advanced"],
                optional=True,  # TO FIX: to prevent dependency cycles
            ),
            openpaperwork_core.Dependency(
                interface=DocStorage,
                defaults=['paperwork_backend.model.workdir'],
            ),
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=["openpaperwork_gtk.fs.gio"],
            ),
            openpaperwork_core.Dependency(
                interface=Index,
                defaults=['paperwork_backend.index.whoosh'],
            ),
            openpaperwork_core.Dependency(
                interface=DocList,
                defaults=['paperwork_gtk.mainwindow.doclist'],
            ),
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=['openpaperwork_gtk.mainloop.glib'],
            ),
            openpaperwork_core.Dependency(
                interface=WorkQueue,
                defaults=['openpaperwork_core.work_queue.default'],
            ),
            openpaperwork_core.Dependency(
                interface=Screenshot,
                defaults=['openpaperwork_gtk.screenshots'],
            ),
            openpaperwork_core.Dependency(
                interface=SearchResultsListener,
                defaults=[],
                optional=True,
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.search_entry = None
        self.widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.mainwindow.search", "field.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.search_entry = self.widget_tree.get_object("search_entry")
        search_field = self.widget_tree.get_object("search_field")

        self.core.call_all(DocList.doclist_add, search_field, vposition=0)

        self.search_entry.connect(
            "search-changed", self.search_update_document_list
        )
        self.search_entry.connect("stop-search", lambda w: self.search_stop())

        self.widget_tree.get_object("search_dialog_button").connect(
            "clicked", lambda button: self.core.call_all(
                AdvancedSearchDialog.gtk_open_advanced_search_dialog
            )
        )

        self.core.call_all(WorkQueue.work_queue_create, "doc_search")
        self.core.call_one(
            Mainloop.mainloop_schedule, self.search_update_document_list
        )

    def search_update_document_list(self, _=None):
        query = self.search_entry.get_text()
        LOGGER.info("Looking for [%s]", query)
        self.core.call_all(Search.search_by_keywords, query)

    def search_get(self):
        return self.search_entry.get_text()

    def search_set(self, text):
        self.search_entry.set_text(text)

    def search_by_keywords(self, query):
        self.core.call_all(WorkQueue.work_queue_cancel_all, "doc_search")
        self.core.call_all(SearchResultsListener.on_search_start, query)
        if query == "":
            out = []
            promise = openpaperwork_core.promise.ThreadedPromise(
                self.core, lambda: self.core.call_all(
                    DocStorage.storage_get_all_docs, out
                )
            )
        else:
            out = []
            promise = openpaperwork_core.promise.ThreadedPromise(
                self.core, lambda: self.core.call_all(
                    Index.index_search, out, query
                )
            )
        promise = promise.then(lambda *args, **kwargs: out)
        promise = promise.then(lambda docs: sorted(docs, reverse=True))

        def show_if_query_still_valid(docs):
            # While we were looking for the documents, the query may have
            # changed (user tying). No point in displaying obsolete results.
            if query != self.search_entry.get_text():
                return
            self.core.call_all(SearchResultsListener.on_search_results, query, docs)

        promise = promise.then(show_if_query_still_valid)

        self.core.call_all(WorkQueue.work_queue_add_promise, "doc_search", promise)

    def search_stop(self):
        self.core.call_all(WorkQueue.work_queue_cancel_all, "doc_search")

    def doc_transaction_start(self, out: list, total_expected=-1):
        class RefreshTransaction(paperwork_backend.sync.BaseTransaction):
            priority = -100000

            def commit(s):
                self.core.call_one(
                    Mainloop.mainloop_schedule, self.search_update_document_list
                )

        out.append(RefreshTransaction(self.core, total_expected))

    def sync(self, promises: list):
        # If someone requested a sync, assume something has changed
        # --> try to keep the view as up-to-date as possible.
        self.search_update_document_list()

        promises.append(openpaperwork_core.promise.Promise(
            self.core, self.search_update_document_list
        ))

    def screenshot_snap_all_doc_widgets(self, out_dir):
        self.core.call_success(
            Screenshot.screenshot_snap_widget, self.search_entry,
            self.core.call_success(Fs.fs_join, out_dir, "search.png"),
            margins=(50, 50, 50, 140)
        )
        self.core.call_success(
            Screenshot.screenshot_snap_widget,
            self.widget_tree.get_object("search_dialog_button"),
            self.core.call_success(
                Fs.fs_join, out_dir, "advanced_search_button.png"
            ),
            margins=(200, 30, 30, 30)
        )

    def search_focus(self):
        LOGGER.info("Focusing on search field")
        self.widget_tree.get_object("search_entry").grab_focus()

    def search_field_add(self, widget):
        search_field = self.widget_tree.get_object("search_field")
        search_field.add(widget)
