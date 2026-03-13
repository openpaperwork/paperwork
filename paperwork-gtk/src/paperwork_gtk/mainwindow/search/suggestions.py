import logging

import openpaperwork_core
from openpaperwork_core.interfaces.work_queue import WorkQueue
import openpaperwork_core.promise

from openpaperwork_gtk.interfaces.gtk import GtkResources

from paperwork_backend.interfaces.docs import DocOpener
from paperwork_backend.interfaces.suggestions import SuggestionProvider

from paperwork_gtk.interfaces.search_field import Search
from paperwork_gtk.interfaces.search_field import SearchField


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    DocOpener,
    Search,
):
    PRIORITY = -2000000

    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
            openpaperwork_core.Dependency(
                interface=SearchField,
                defaults=['paperwork_gtk.mainwindow.search.field'],
            ),
            openpaperwork_core.Dependency(
                interface=SuggestionProvider,
                defaults=['paperwork_backend.index.whoosh'],
            ),
            openpaperwork_core.Dependency(
                interface=WorkQueue,
                defaults=["openpaperwork_core.work_queue.default"],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.mainwindow.search", "suggestions.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        suggestion_revealer = self.widget_tree.get_object(
            "suggestions_revealer"
        )
        self.core.call_all(SearchField.search_field_add, suggestion_revealer)

        self.widget_tree.get_object("button_close").connect(
            "clicked", self._close
        )
        self.widget_tree.get_object("treeview_suggestions").connect(
            "row-activated", self._on_row_activated
        )

    def _get_suggestions(self, query):
        out = set()
        self.core.call_all(SuggestionProvider.suggestion_get, out, query)
        out = list(out)
        out.sort()
        return out

    def _show_suggestions(self, suggestions, query):
        if query != self.core.call_success(SearchField.search_get):
            # Text has changed while we were looking for suggestions
            # No point in displaying them now.
            return
        LOGGER.info("%d suggestions found", len(suggestions))
        model = self.widget_tree.get_object("liststore_suggestions")
        model.clear()
        for suggestion in suggestions:
            model.append((suggestion,))
        self.widget_tree.get_object(
            "suggestions_revealer"
        ).set_reveal_child(len(suggestions) > 0)

    def search_by_keywords(self, query):
        self.widget_tree.get_object("liststore_suggestions").clear()

        self.widget_tree.get_object(
            "suggestions_revealer"
        ).set_reveal_child(False)

        if query == "":
            return

        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self._get_suggestions, args=(query,)
        )
        promise = promise.then(self._show_suggestions, query)
        self.core.call_success(
            WorkQueue.work_queue_add_promise, "doc_search", promise
        )

    def _close(self, *args, **kwargs):
        self.widget_tree.get_object(
            "suggestions_revealer"
        ).set_reveal_child(False)

    def doc_open(self, *args, **kwargs):
        self._close()

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    @openpaperwork_core.noop
    def doc_close(self):
        pass

    def _on_row_activated(self, treeview, path, column):
        model = treeview.get_model()
        suggestion = model[path][0]
        self.core.call_all(SearchField.search_set, suggestion)

    @openpaperwork_core.noop
    def search_update_document_list(self, _=None):
        pass

    @openpaperwork_core.noop
    def search_stop(self):
        pass
