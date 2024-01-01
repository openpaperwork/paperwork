import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "page_redo_ocr"


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.active_doc = (None, None)
        self.active_page_idx = -1
        self.action = None

    def get_interfaces(self):
        return [
            'action',
            'action_page',
            'action_page_redo_ocr',
            'chkdeps',
            'doc_open',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'ocr',
                'defaults': ['paperwork_backend.guesswork.ocr.pyocr'],
            },
            {
                'interface': 'ocr_settings',
                'defaults': ['paperwork_backend.pyocr'],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def init(self, core):
        super().init(core)
        if not GLIB_AVAILABLE:
            return

        self.item = Gio.MenuItem.new(
            _("Redo OCR on page"), "win." + ACTION_NAME
        )

        self.action = Gio.SimpleAction.new(ACTION_NAME, None)
        self.action.connect("activate", self._redo_ocr)
        self.core.call_all("app_actions_add", self.action)

        self._update_sensitivity()
        self.core.call_all(
            "ocr_add_observer_on_enabled",
            self._update_sensitivity
        )

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def doc_close(self):
        self.active_doc = (None, None)

    def _update_sensitivity(self):
        enabled = self.core.call_success("ocr_is_enabled")
        self.action.set_enabled(enabled is not None)

    def on_page_shown(self, page_idx):
        self.active_page_idx = page_idx

    def _redo_ocr(self, *args, **kwargs):
        (doc_id, doc_url) = self.active_doc
        page_idx = self.active_page_idx

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all,
            args=(
                "on_progress", "redo_ocr", 0.0,
                _("OCR on {doc_id} p{page_idx}").format(
                    doc_id=doc_id, page_idx=page_idx
                )
            )
        )
        promise = promise.then(lambda *args, **kwargs: None)

        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, self.core.call_all,
            args=("ocr_page_by_url", doc_url, page_idx,)
        ))
        promise = promise.then(lambda *args, **kwargs: None)

        promise = promise.then(
            self.core.call_all, "on_progress", "redo_ocr", 1.0
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self.core.call_success(
            "transaction_simple_promise", [('upd', doc_id),]
        ))
        self.core.call_success("transaction_schedule", promise)
