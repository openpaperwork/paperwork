import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.progress import ProgressListener
import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise

from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.docs import DocOpener
from paperwork_backend.interfaces.ocr import Ocr
from paperwork_backend.interfaces.ocr import OcrSettings

from paperwork_gtk import _
from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector
from paperwork_gtk.interfaces.doc_viewer import PageViewerListener


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "page_redo_ocr"


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
                'interface': DocTransactionManager,
                'defaults': ['paperwork_backend.sync'],
            },
            {
                'interface': Ocr,
                'defaults': ['paperwork_backend.guesswork.ocr.pyocr'],
            },
            {
                'interface': OcrSettings,
                'defaults': ['paperwork_backend.pyocr'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.active_doc = (None, None)
        self.active_page_idx = -1
        self.action = None
        if not GLIB_AVAILABLE:
            return

        self.item = Gio.MenuItem.new(
            _("Redo OCR on page"), "win." + ACTION_NAME
        )

        self.action = Gio.SimpleAction.new(ACTION_NAME, None)
        self.action.connect("activate", self._redo_ocr)
        self.core.call_all(AppActionCollector.app_actions_add, self.action)

        self._update_sensitivity()
        self.core.call_all(
            OcrSettings.ocr_add_observer_on_enabled,
            self._update_sensitivity
        )

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    def doc_close(self):
        self.active_doc = (None, None)

    def _update_sensitivity(self):
        enabled = self.core.call_success(OcrSettings.ocr_is_enabled)
        self.action.set_enabled(enabled is not None)

    def on_page_shown(self, page_idx):
        self.active_page_idx = page_idx

    def _redo_ocr(self, *args, **kwargs):
        (doc_id, doc_url) = self.active_doc
        page_idx = self.active_page_idx

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all,
            args=(
                ProgressListener.on_progress, "redo_ocr", 0.0,
                _("OCR on {doc_id} p{page_idx}").format(
                    doc_id=doc_id, page_idx=page_idx
                )
            )
        )
        promise = promise.then(lambda *args, **kwargs: None)

        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, self.core.call_all,
            args=(Ocr.ocr_page_by_url, doc_url, page_idx,)
        ))
        promise = promise.then(lambda *args, **kwargs: None)

        promise = promise.then(
            self.core.call_all, ProgressListener.on_progress, "redo_ocr", 1.0
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self.core.call_success(
            DocTransactionManager.transaction_simple_promise, [('upd', doc_id),]
        ))
        self.core.call_success(DocTransactionManager.transaction_schedule, promise)

    @openpaperwork_core.noop
    def on_page_size_obtained(self, page):
        pass
