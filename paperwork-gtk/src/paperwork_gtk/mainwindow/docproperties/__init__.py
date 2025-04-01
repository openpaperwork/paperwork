import logging

import openpaperwork_core
import openpaperwork_core.promise

LOGGER = logging.getLogger(__name__)


class DocPropertiesUpdate(object):
    def __init__(self, doc_id, multiple_docs=False):
        self.doc_id = doc_id
        self.multiple_docs = multiple_docs

        self.new_docs = set()
        self.upd_docs = set()
        self.del_docs = set()


class DocPropertiesEditor(object):
    def __init__(self, name, plugin, multiple_docs=False):
        self.name = name
        self.core = plugin.core
        self.plugin = plugin
        self.multiple_docs = multiple_docs

        self.active_docs = set()

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docproperties", "docproperties.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.widget_tree.get_object("docproperties_back").connect(
            "clicked", self._apply
        )
        self.widget_tree.get_object("docproperties_cancel").connect(
            "clicked", self._cancel
        )

        self.core.call_all(
            "mainwindow_add", side="left", name="docproperties_" + self.name,
            prio=0,
            header=self.widget_tree.get_object("docproperties_header"),
            body=self.widget_tree.get_object("docproperties_body"),
        )

        self.core.call_one(
            "mainloop_schedule", self._build_doc_properties,
            multiple_docs
        )

    def show(self):
        self.core.call_all(
            "mainwindow_show", side="left", name="docproperties_" + self.name
        )

    def hide(self):
        self.core.call_all("mainwindow_back", side="left")

    def _build_doc_properties(self, multiple_docs):
        components = []
        self.core.call_all(
            "doc_properties_components_get", components,
            multiple_docs=multiple_docs
        )
        for component in components:
            self.widget_tree.get_object("docproperties_box").pack_start(
                component, expand=False, fill=True, padding=0
            )

    def doc_open(self, doc_id, doc_url):
        self.active_docs = {(doc_id, doc_url)}
        self.core.call_all(
            "doc_properties_components_set_active_doc", doc_id, doc_url
        )

    def docs_open(self, docs):
        self.active_docs = docs
        self.core.call_all(
            "doc_properties_components_set_active_docs", docs
        )

    def _open_doc(self, upd):
        active_docs = {doc[0] for doc in self.active_docs}
        if upd.doc_id is not None and upd.doc_id not in active_docs:
            doc_url = self.core.call_success("doc_id_to_url", upd.doc_id)
            if doc_url is None:
                return
            self.core.call_all("doc_open", upd.doc_id, doc_url)

    def _apply(self, *args, **kwargs):
        LOGGER.info(
            "Changes validated by the user (multiple_docs=%s)",
            self.multiple_docs
        )
        upd = DocPropertiesUpdate(
            list(self.active_docs)[0][0], self.multiple_docs
        )

        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self.core.call_all,
            args=("doc_properties_components_apply_changes", upd)
        )
        # drop call_all return value
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self._open_doc, upd)
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self.core.call_all, "search_update_document_list"
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self._upd_index, upd)
        promise.schedule()

        self.core.call_all("close_doc_properties")

    def _cancel(self, *args, **kwargs):
        LOGGER.info("Changes cancelled by the user")
        self.core.call_all("doc_properties_components_cancel_changes")
        self.core.call_all("close_doc_properties")

    def _upd_index(self, upd):
        total = len(upd.new_docs) + len(upd.upd_docs) + len(upd.del_docs)

        if total <= 0:
            LOGGER.info("Document %s not modified. Nothing to do", upd.doc_id)
            return

        LOGGER.info(
            "Document %s modified. %d documents impacted", upd.doc_id, total
        )

        changes = []
        for doc_id in upd.new_docs:
            changes.append(('add', doc_id))
        for doc_id in upd.upd_docs:
            changes.append(('upd', doc_id))
        for doc_id in upd.del_docs:
            changes.append(('del', doc_id))
        self.core.call_success("transaction_simple", changes)

    def docproperties_scroll_to_last(self):
        scroll = self.widget_tree.get_object("docproperties_body")
        vadj = scroll.get_vadjustment()
        vadj.set_value(vadj.get_upper())


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['gtk_doc_properties']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_mainwindow',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.editors = {
            'single_doc': DocPropertiesEditor(
                "single", self, multiple_docs=False
            ),
            'multiple_docs': DocPropertiesEditor(
                "multiple", self, multiple_docs=True
            ),
        }

        self.active_editor = None

    def doc_open(self, doc_id, doc_url):
        if self.active_editor is None:
            return
        e = self.active_editor
        e.doc_open(doc_id, doc_url)

    def open_doc_properties(self, doc_id, doc_url):
        assert self.active_editor is None
        e = self.editors['single_doc']
        self.active_editor = e
        e.doc_open(doc_id, doc_url)
        e.show()

    def open_docs_properties(self, docs):
        assert self.active_editor is None
        e = self.editors['multiple_docs']
        self.active_editor = e
        e.docs_open(docs)
        e.show()

    def close_doc_properties(self):
        assert self.active_editor is not None
        self.active_editor.hide()
        self.active_editor = None

    def docproperties_scroll_to_last(self):
        for e in self.editors.values():
            e.docproperties_scroll_to_last()
