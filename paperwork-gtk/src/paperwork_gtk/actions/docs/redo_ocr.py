import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.progress import ProgressListener
import openpaperwork_core
import openpaperwork_core.promise

from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.docs import Docs
from paperwork_backend.interfaces.ocr import Ocr, OcrSettings

from paperwork_gtk import _
from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector
from paperwork_gtk.interfaces.doc_selection import DocSelection


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_redo_ocr_many"


class Plugin(
    openpaperwork_core.PluginBase,
    AppAction,
    Chkdeps,
):
    PRIORITY = -40

    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            {
                'interface': AppActionCollector,
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                "interface": Docs,
                "defaults": ["paperwork_backend.model"],
            },
            {
                'interface': DocSelection,
                'defaults': ['paperwork_gtk.doc_selection'],
            },
            {
                'interface': Ocr,
                'defaults': ['paperwork_backend.guesswork.ocr.pyocr'],
            },
            {
                'interface': OcrSettings,
                'defaults': ['paperwork_backend.pyocr'],
            },
            {
                'interface': DocTransactionManager,
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        if not GLIB_AVAILABLE:
            return
        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._redo_ocr_many)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _redo_ocr_single(
            self, doc_id, doc_url,
            progression_start_page_idx, progression_total_pages):
        nb_pages = self.core.call_success(Docs.doc_get_nb_pages_by_url, doc_url)
        if nb_pages is None:
            LOGGER.warning("No pages in document %s. Nothing to do", doc_id)
            return

        LOGGER.info(
            "Will redo OCR on document %s (nb pages = %d)", doc_id, nb_pages
        )

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all,
            args=(
                ProgressListener.on_progress, "redo_ocr",
                progression_start_page_idx / progression_total_pages,
                _("OCR on %s") % doc_id)
        )
        promise = promise.then(lambda *args, **kwargs: None)

        for page_idx in range(0, nb_pages):
            promise = promise.then(
                self.core.call_all, ProgressListener.on_progress, "redo_ocr",
                (progression_start_page_idx + page_idx) /
                progression_total_pages,
                _("OCR on {doc_id} p{page_idx}").format(
                    doc_id=doc_id, page_idx=(page_idx + 1)
                )
            )
            promise = promise.then(lambda *args, **kwargs: None)
            promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
                self.core, self.core.call_all,
                args=(Ocr.ocr_page_by_url, doc_url, page_idx,)
            ))
            promise = promise.then(lambda *args, **kwargs: None)

        promise = promise.then(
            self.core.call_all, ProgressListener.on_progress, "redo_ocr",
            (progression_start_page_idx + nb_pages) /
            progression_total_pages,
        )
        promise = promise.then(lambda *args, **kwargs: None)

        promise = promise.then(self.core.call_success(
            DocTransactionManager.transaction_simple_promise, [('upd', doc_id),]
        ))
        return (promise, nb_pages)

    def _redo_ocr_many(self, action, parameter):
        docs = set()
        self.core.call_all(DocSelection.doc_selection_get, docs)

        total_pages = 0
        for (doc_id, doc_url) in docs:
            nb_pages = self.core.call_success(
                Docs.doc_get_nb_pages_by_url, doc_url
            )
            if nb_pages is None:
                nb_pages = 0
            total_pages += nb_pages

        promise = openpaperwork_core.promise.Promise(self.core)
        nb_all_pages = 0
        for (doc_id, doc_url) in docs:
            (p, nb_doc_pages) = self._redo_ocr_single(
                doc_id, doc_url, nb_all_pages, total_pages
            )
            nb_all_pages += nb_doc_pages
            promise = promise.then(p)

        self.core.call_success(DocTransactionManager.transaction_schedule, promise)
