import logging

import pyocr
import pyocr.builders

import openpaperwork_core

from ... import (_, sync)


LOGGER = logging.getLogger(__name__)

ID = "ocr"


class OcrTransaction(sync.BaseTransaction):
    def __init__(self, plugin, sync, total_expected=-1):
        super().__init__(plugin.core, total_expected)

        self.priority = plugin.PRIORITY

        self.plugin = plugin
        self.sync = sync

        # for each document, we need to track which pages have already been
        # OCR-ed, which have been modified (cropping, rotation, ...)
        # and must be re-OCRed, and which have not been changed.
        self.page_tracker = self.core.call_success("page_tracker_get", ID)

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()

    def _run_ocr_on_page(
            self, doc_id, doc_url, page_idx, page_nb, total_pages,
            wordless_only=False):
        if wordless_only:
            has_text = self.core.call_success(
                "page_has_text_by_url", doc_url, page_idx
            )
            if has_text:
                # there is already some text on this page
                self.notify_progress(
                    ID,
                    _(
                        "Document {doc_id} p{page_idx} has already some text."
                        " No OCR run"
                    ).format(doc_id=doc_id, page_idx=(page_idx + 1)),
                    page_nb=page_nb, total_pages=total_pages
                )
                return

        self.notify_progress(
            ID,
            _("Running OCR on document {doc_id} p{page_idx}").format(
                doc_id=doc_id, page_idx=(page_idx + 1)
            ),
            page_nb=page_nb, total_pages=total_pages
        )
        self.plugin.ocr_page_by_url(doc_url, page_idx)

    def _run_ocr_on_modified_pages(self, doc_id, wordless_only=False):
        doc_url = self.core.call_success("doc_id_to_url", doc_id)

        need_end_notification = False
        modified_pages = list(self.page_tracker.find_changes(doc_id, doc_url))
        for (page_nb, (change, page_idx)) in enumerate(modified_pages):
            # Run OCR on modified pages, but only if we are not synchronizing
            # with the work directory (--> if the user just added or modified
            # a document)
            if not self.sync and (change == 'new' or change == 'upd'):
                self._run_ocr_on_page(
                    doc_id, doc_url, page_idx, page_nb, len(modified_pages),
                    wordless_only
                )
                need_end_notification = True
            self.page_tracker.ack_page(doc_id, doc_url, page_idx)

        if need_end_notification:
            self.notify_progress(
                ID, _("Running OCR"),
                page_nb=len(modified_pages), total_pages=len(modified_pages)
            )

    def add_doc(self, doc_id):
        self._run_ocr_on_modified_pages(doc_id, wordless_only=True)
        super().add_doc(doc_id)

    def upd_doc(self, doc_id):
        self._run_ocr_on_modified_pages(doc_id, wordless_only=True)
        super().upd_doc(doc_id)

    def del_doc(self, doc_id):
        self.page_tracker.delete_doc(doc_id)
        super().del_doc(doc_id)

    def cancel(self):
        self.page_tracker.cancel()
        self.notify_done(ID)

    def commit(self):
        self.page_tracker.commit()
        self.notify_done(ID)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    def get_interfaces(self):
        return [
            "ocr",
            "syncable",  # actually satisfied by the plugin 'doctracker'
        ]

    def get_deps(self):
        return [
            {
                'interface': 'doc_tracking',
                'defaults': ['paperwork_backend.doctracker'],
            },
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'ocr_settings',
                'defaults': ['paperwork_backend.pyocr'],
            },
            {
                'interface': 'page_boxes',
                'defaults': [
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.pdf',
                ],
            },
            {
                'interface': 'page_tracking',
                'defaults': ['paperwork_backend.pagetracker'],
            },
            {
                'interface': 'pillow',
                'defaults': [
                    'openpaperwork_core.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ],
            },
        ]

    def init(self, core):
        super().init(core)
        self.core.call_all(
            "doc_tracker_register", ID,
            lambda sync, total_expected=-1: OcrTransaction(
                self, sync, total_expected
            )
        )

    def ocr_page_by_url(self, doc_url, page_idx):
        if self.core.call_success("ocr_is_enabled") is None:
            LOGGER.info("OCR is disabled")
            return

        LOGGER.info("Running OCR on page %d of %s", page_idx, doc_url)

        doc_id = self.core.call_success("doc_url_to_id", doc_url)
        if doc_id is not None:
            self.core.call_one(
                "mainloop_schedule", self.core.call_all,
                "on_page_modification_start", doc_id, page_idx
            )
        try:
            page_img_url = self.core.call_success(
                "page_get_img_url", doc_url, page_idx
            )
            ocr_tool = pyocr.get_available_tools()[0]
            LOGGER.info(
                "Will use tool '%s' on %s p%d (%s)",
                ocr_tool.get_name(), doc_url, page_idx, page_img_url
            )

            ocr_langs = self.core.call_success("ocr_get_active_langs")

            img = self.core.call_success("url_to_pillow", page_img_url)

            boxes = ocr_tool.image_to_string(
                img, lang="+".join(ocr_langs),
                builder=pyocr.builders.LineBoxBuilder()
            )
            self.core.call_success(
                "page_set_boxes_by_url", doc_url, page_idx, boxes
            )
        except Exception as exc:
            LOGGER.error("OCR FAILED", exc_info=exc)
        finally:
            if doc_id is not None:
                self.core.call_one(
                    "mainloop_schedule", self.core.call_all,
                    "on_page_modification_end", doc_id, page_idx
                )

        return True
