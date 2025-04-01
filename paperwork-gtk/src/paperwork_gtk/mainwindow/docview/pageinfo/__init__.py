import logging

import openpaperwork_core
import paperwork_backend.sync


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'doc_open',
            'gtk_docview_pageinfo',
            'syncable',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'gtk_docview',
                'defaults': ['paperwork_gtk.mainwindow.docview'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.page_info = None
        self.active_doc = (None, None)
        self.nb_pages = None
        self.current_page = None
        self.nb_pages = None

        self.core.call_success(
            "gtk_load_css",
            "paperwork_gtk.mainwindow.docview.pageinfo", "pageinfo.css"
        )

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview.pageinfo", "pageinfo.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.page_info = self.widget_tree.get_object("page_info")
        self.current_page = self.widget_tree.get_object(
            "page_current_nb"
        )
        self.current_page.connect("activate", self._change_page)
        self.nb_pages = self.widget_tree.get_object("page_total")

        button = self.widget_tree.get_object("page_prev")
        button.connect(
            "clicked",
            lambda *args, **kwargs: self.core.call_all(
                "doc_goto_previous_page"
            )
        )
        button = self.widget_tree.get_object("page_next")
        button.connect(
            "clicked",
            lambda *args, **kwargs: self.core.call_all("doc_goto_next_page")
        )

        self.core.call_success("docview_get_body").add_overlay(self.page_info)

        def _set_docview_margin(page_info, size_allocation):
            self.core.call_all(
                "docview_set_bottom_margin", page_info.get_allocated_height()
            )

        self.page_info.connect("size-allocate", _set_docview_margin)

    def _change_page(self, *args, **kwargs):
        txt = self.current_page.get_text()
        if txt == "":
            return
        self.core.call_all("doc_goto_page", int(txt) - 1)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages is None:
            nb_pages = 0

        self.current_page.set_text("")
        self.nb_pages.set_text(f"/ {nb_pages}")
        self.page_info.set_visible(True)
        self.page_info.set_sensitive(nb_pages > 0)

    def doc_reload(self, doc_id, doc_url):
        if (doc_id, doc_url) != self.active_doc:
            return
        self.doc_open(*self.active_doc)

    def on_page_shown(self, page_idx):
        txt = str(page_idx + 1)
        if txt != self.current_page.get_text():
            self.current_page.set_text(txt)

    def page_info_add_left(self, widget):
        self.widget_tree.get_object("page_prevnext").pack_end(
            widget, expand=False, fill=True, padding=0
        )
        return True

    def page_info_add_right(self, widget):
        self.widget_tree.get_object("page_info").pack_end(
            widget, expand=False, fill=True, padding=0
        )
        return True

    def doc_transaction_start(self, out: list, total_expected=-1):
        class RefreshTransaction(paperwork_backend.sync.BaseTransaction):
            priority = -100000

            def __init__(s, core, total_expected=-1):
                super().__init__(core, total_expected)
                s.active_doc = False

            def _refresh(s):
                self.core.call_success(
                    "mainloop_schedule", self.doc_open, *self.active_doc
                )
                s.active_doc = True

            def add_doc(s, doc_id):
                if self.active_doc[0] == doc_id:
                    s._refresh()

            def upd_doc(s, doc_id):
                if self.active_doc[0] == doc_id:
                    s._refresh()

            def del_doc(s, doc_id):
                if self.active_doc[0] == doc_id:
                    s._refresh()

            def cancel(s):
                if s.active_doc:
                    s._refresh()

            def commit(s):
                if s.active_doc:
                    s._refresh()

        out.append(RefreshTransaction(self.core, total_expected))

    def sync(self, promises: list):
        # sync don't change document content --> no need to refresh
        pass
