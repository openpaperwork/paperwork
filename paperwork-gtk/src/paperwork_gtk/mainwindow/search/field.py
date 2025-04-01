import logging

import openpaperwork_core
import openpaperwork_core.promise
import paperwork_backend.sync


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -1000000

    @classmethod
    def get_interfaces(cls):
        return [
            'gtk_search_field',
            'screenshot_provider',
            'syncable',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'index',
                'defaults': ['paperwork_backend.index.whoosh'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'work_queue',
                'defaults': ['openpaperwork_core.work_queue.default'],
            },
            {
                'interface': 'screenshot',
                'defaults': ['openpaperwork_gtk.screenshots'],
            },
            {
                'interface': 'thread',
                'defaults': ['openpaperwork_core.thread.simple'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.search_entry = None
        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.search", "field.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.search_entry = self.widget_tree.get_object("search_entry")
        search_field = self.widget_tree.get_object("search_field")

        self.core.call_all("doclist_add", search_field, vposition=0)

        self.search_entry.connect(
            "search-changed", self.search_update_document_list
        )
        self.search_entry.connect("stop-search", lambda w: self.search_stop())

        self.widget_tree.get_object("search_dialog_button").connect(
            "clicked", lambda button: self.core.call_all(
                "gtk_open_advanced_search_dialog"
            )
        )

        self.core.call_all("work_queue_create", "doc_search")
        self.core.call_one(
            "mainloop_schedule", self.search_update_document_list
        )

    def search_update_document_list(self, _=None):
        query = self.search_entry.get_text()
        LOGGER.info("Looking for [%s]", query)
        self.core.call_all("search_by_keywords", query)

    def search_get(self):
        return self.search_entry.get_text()

    def search_set(self, text):
        self.search_entry.set_text(text)

    def search_by_keywords(self, query):
        self.core.call_all("work_queue_cancel_all", "doc_search")
        self.core.call_all("on_search_start", query)
        if query == "":
            out = []
            promise = openpaperwork_core.promise.ThreadedPromise(
                self.core, lambda: self.core.call_all(
                    "storage_get_all_docs", out
                )
            )
        else:
            out = []
            promise = openpaperwork_core.promise.ThreadedPromise(
                self.core, lambda: self.core.call_all(
                    "index_search", out, query
                )
            )
        promise = promise.then(lambda *args, **kwargs: out)
        promise = promise.then(lambda docs: sorted(docs, reverse=True))

        def show_if_query_still_valid(docs):
            # While we were looking for the documents, the query may have
            # changed (user tying). No point in displaying obsolete results.
            if query != self.search_entry.get_text():
                return
            self.core.call_all("on_search_results", query, docs)

        promise = promise.then(show_if_query_still_valid)

        self.core.call_all("work_queue_add_promise", "doc_search", promise)

    def search_stop(self):
        self.core.call_all("work_queue_cancel_all", "doc_search")

    def doc_transaction_start(self, out: list, total_expected=-1):
        class RefreshTransaction(paperwork_backend.sync.BaseTransaction):
            priority = -100000

            def commit(s):
                self.core.call_one(
                    "mainloop_schedule", self.search_update_document_list
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
            "screenshot_snap_widget", self.search_entry,
            self.core.call_success("fs_join", out_dir, "search.png"),
            margins=(50, 50, 50, 140)
        )
        self.core.call_success(
            "screenshot_snap_widget",
            self.widget_tree.get_object("search_dialog_button"),
            self.core.call_success(
                "fs_join", out_dir, "advanced_search_button.png"
            ),
            margins=(200, 30, 30, 30)
        )

    def search_focus(self):
        LOGGER.info("Focusing on search field")
        self.widget_tree.get_object("search_entry").grab_focus()

    def search_field_add(self, widget):
        search_field = self.widget_tree.get_object("search_field")
        search_field.add(widget)
