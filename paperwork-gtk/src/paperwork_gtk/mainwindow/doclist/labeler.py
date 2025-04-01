import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)


class LabelingTask(object):
    def __init__(self, plugin, doc_id, doc_url, flowlayout):
        self.plugin = plugin
        self.core = plugin.core

        self.doc_id = doc_id
        self.doc_url = doc_url
        self.flowlayout = flowlayout

    def show_labels(self, labels):
        for widget in list(self.flowlayout.get_children()):
            if hasattr(widget, 'txt'):
                self.flowlayout.remove(widget)

        labels = [
            (
                self.core.call_success("i18n_strip_accents", label[0].lower()),
                label[0],
                label[1]
            ) for label in labels
        ]
        labels.sort()

        for label in labels:
            try:
                color = self.core.call_success("label_color_to_rgb", label[2])
            except Exception as exc:
                LOGGER.warning(
                    "Invalid label %s on document %s", label, self.doc_id,
                    exc_info=exc
                )
                continue
            widget = self.core.call_success(
                "gtk_widget_label_new", label[1], color
            )
            widget.set_visible(True)
            self.flowlayout.add_child(widget, Gtk.Align.END)

    def get_promise(self):
        promise = openpaperwork_core.promise.Promise(
            self.core,
            LOGGER.info, args=("Loading labels of document %s", self.doc_id,)
        )
        promise = promise.then(lambda *args: None)  # drop logger return value

        promises = []
        self.core.call_all(
            "doc_get_labels_by_url_promise",
            promises, self.doc_url
        )
        for p in promises:
            promise = promise.then(p)

        return promise.then(self.show_labels)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    @classmethod
    def get_interfaces(cls):
        return [
            'gtk_doclist_listener',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'doc_labels',
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.maindow.doclist'],
            },
            {
                'interface': 'gtk_widget_label',
                'defaults': ['paperwork_gtk.widget.label'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
            {
                'interface': 'work_queue',
                'defaults': ['openpaperwork_core.work_queue.default'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.default_thumbnail = None
        self.running = False
        self.tasks = {}
        self.processing_docs = set()
        self.processed_docs = set()
        self.core.call_all("work_queue_create", "labeler", stop_on_quit=True)

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def doclist_show(self, docs):
        self.core.call_all("work_queue_cancel_all", "labeler")
        self.task = {}

    def on_doc_list_clear(self):
        self.processed_docs = set()
        self.on_doc_list_visibility_changed()

    def on_doc_list_visibility_changed(self):
        self.core.call_all("work_queue_cancel_all", "labeler")
        self.processing_docs = set()
        self.nb_to_load = 0

    def on_doc_box_visible(self, doc_id, gtk_row, gtk_custom_flowlayout):
        if doc_id in self.processing_docs:
            return
        if doc_id in self.processed_docs:
            return

        self.processing_docs.add(doc_id)

        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        if doc_url is None:
            return

        task = LabelingTask(self, doc_id, doc_url, gtk_custom_flowlayout)
        self.tasks[doc_url] = task

        def _when_loaded():
            if doc_id in self.processing_docs:
                self.processing_docs.remove(doc_id)
                self.processed_docs.add(doc_id)

        promise = task.get_promise()
        promise = promise.then(_when_loaded)

        self.core.call_success("work_queue_add_promise", "labeler", promise)

    def _refresh_doc(self, doc_url):
        if doc_url not in self.tasks:
            LOGGER.debug(
                "Labels on '%s' have changed, but it is not displayed at"
                " the moment", doc_url
            )
            return
        LOGGER.info("Reloading labels of '%s'", doc_url)
        self.core.call_success(
            "work_queue_add_promise", "labeler",
            self.tasks[doc_url].get_promise()
        )

    def doc_add_label_by_url(self, doc_url, label, color=None):
        self._refresh_doc(doc_url)

    def doc_remove_label_by_url(self, doc_url, label):
        self._refresh_doc(doc_url)
