import logging

from openpaperwork_core.interfaces.chkdeps import Chkdeps

try:
    import gi
    gi.require_version('Gdk', '3.0')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gdk
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.promise
import openpaperwork_gtk.deps

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.docs import DocOpener
from paperwork_backend.interfaces.pages import PageManagement

from paperwork_gtk.interfaces.doc_import import DocImport
from paperwork_gtk.interfaces.drag_n_drop import DragAndDrop
from paperwork_gtk.interfaces.drag_n_drop import DragAndDropDestination


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    DocOpener,
    DragAndDrop,
):
    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            openpaperwork_core.Dependency(
                interface=DocImport,
                defaults=["paperwork_gtk.docimport"],
            ),
            openpaperwork_core.Dependency(
                interface=DocOpener,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=DocStorage,
                defaults=['paperwork_backend.model.workdir'],
            ),
            openpaperwork_core.Dependency(
                interface=DocTransactionManager,
                defaults=['paperwork_backend.sync'],
            ),
            openpaperwork_core.Dependency(
                interface=DragAndDropDestination,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=PageManagement,
                defaults=[
                    "paperwork_backend.model.img",
                    "paperwork_backend.model.hocr",
                    "paperwork_backend.model.pdf",
                ],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.active_doc = (None, None)
        self.updated = set()
        self.promise = openpaperwork_core.promise.Promise(self.core)

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def _parse_paperwork_uri(self, uri):
        infos = uri.split("#", 1)[1]
        infos = infos.split("&")
        infos = (i.split("=", 1) for i in infos)
        infos = {k: v for (k, v) in infos}
        return (infos['doc_id'], int(infos['page']))

    def doc_close(self):
        self.active_doc = (None, None)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    def drag_and_drop_page_enable(self, widget):
        widget.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.MOVE)
        targets = Gtk.TargetList.new([])
        targets.add_uri_targets(0)
        widget.drag_dest_set_target_list(targets)
        widget.connect("drag-data-received", self._on_drag_data_received)

    def _on_drag_data_received(
            self, widget, drag_context, x, y, selection_data, info, time):
        uris = selection_data.get_uris()
        LOGGER.info(
            "drag_data_received(%s, %d, %d, %s, %s)",
            widget, x, y, uris, info
        )

        dst = self.core.call_success(
            DragAndDropDestination.drag_and_drop_get_destination, widget, x, y
        )
        if dst is None:
            LOGGER.error("Nobody accepted a drop on %s (%d, %d)", widget, x, y)
            return

        (dst_doc_id, dst_doc_url, dst_page_idx) = dst

        for uri in reversed(uris):
            LOGGER.info("Drop: URI: %s", uri)

            self.core.call_all(
                DragAndDrop.drag_and_drop_page_add,
                uri, dst_doc_id, dst_doc_url, dst_page_idx
            )

        self.core.call_all(DragAndDrop.drag_and_drop_apply)

    def drag_and_drop_page_add(self, src_uri, dst_doc_id, dst_doc_url, dst_page_idx):
        LOGGER.info("Drop: %s --> %s p%d", src_uri, dst_doc_id, dst_page_idx)

        if "doc_id=" not in src_uri or "page=" not in src_uri:
            LOGGER.info("Drop: Import of %s", src_uri)
            # TODO(Jflesch): Should import to the target document (drop)
            # instead of the currently-opened document
            self.core.call_all(DocImport.gtk_doc_import, [src_uri])
            return
        else:
            # moving page inside the current document
            (src_doc_id, src_page_idx) = self._parse_paperwork_uri(src_uri)

        src_doc_url = self.core.call_success(DocStorage.doc_id_to_url, src_doc_id)
        assert src_doc_url is not None

        if src_doc_id == dst_doc_id and src_page_idx < dst_page_idx:
            dst_page_idx -= 1
        dst_page_idx = max(dst_page_idx, 0)

        LOGGER.info(
            "Drop: %s p%d --> %s p%d",
            src_doc_id, src_page_idx,
            dst_doc_id, dst_page_idx
        )

        if src_doc_id == dst_doc_id and src_page_idx == dst_page_idx:
            return

        self.promise = self.promise.then(
            self.core.call_all, PageManagement.page_move_by_url,
            src_doc_url, src_page_idx,
            dst_doc_url, dst_page_idx
        )
        self.promise = self.promise.then(lambda *args, **kwargs: None)

        for doc in ((src_doc_id, src_doc_url), (dst_doc_id, dst_doc_url)):
            self.promise = self.promise.then(
                self.core.call_all, DocOpener.doc_reload
            )
            self.promise = self.promise.then(lambda *args, **kwargs: None)

        self.updated.add(src_doc_id)
        self.updated.add(dst_doc_id)

    def drag_and_drop_apply(self):
        if len(self.updated) <= 0:
            return

        self.promise = self.promise.then(self.core.call_success(
            DocTransactionManager.transaction_simple_promise,
            [('upd', doc_id) for doc_id in self.updated]
        ))
        self.core.call_success(DocTransactionManager.transaction_schedule, self.promise)

        self.updated = set()
        self.promise = openpaperwork_core.promise.Promise(self.core)
