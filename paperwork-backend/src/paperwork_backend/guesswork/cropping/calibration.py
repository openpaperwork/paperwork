"""
Crop scanned images based on a predefined area.
"""

import logging

import openpaperwork_core

from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.pillow import Pillow
from openpaperwork_core.interfaces.progress import ProgressListener

from paperwork_backend import (_, sync)
from paperwork_backend.guesswork.cropping import ID
from paperwork_backend.interfaces.cropping import Cropping
from paperwork_backend.interfaces.cropping import PredefinedCropping
from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.page_modification import PageModificationListener
from paperwork_backend.interfaces.pages import PageImg
from paperwork_backend.interfaces.pages import PageText
from paperwork_backend.interfaces.sync import DocTracker
from paperwork_backend.interfaces.sync import PageTracker


LOGGER = logging.getLogger(__name__)


class CalibrationTransaction(sync.BaseTransaction):
    def __init__(self, plugin, sync, total_expected=-1):
        super().__init__(plugin.core, total_expected)

        self.priority = plugin.PRIORITY

        self.plugin = plugin
        self.sync = sync

        # For each document, we need to track on which pages we have already
        # guessed the page borders and on which page we didn't yet.
        # We use the same ID for all the cropping plugins so we never crop
        # twice the same page.
        self.page_tracker = self.core.call_success(PageTracker.page_tracker_get, ID)

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()

    def _crop_page(self, doc_id, doc_url, page_idx, page_nb, total_pages):
        paper_size = self.core.call_success(
            PageImg.page_get_paper_size_by_url, doc_url, page_idx
        )
        if paper_size is not None:
            # We only want to crop scanned pages.
            self.notify_progress(
                ID,
                _("Document {doc_id} p{page_idx} already cropped").format(
                    doc_id=doc_id, page_idx=(page_idx + 1)
                ),
                page_nb=page_nb, total_pages=total_pages
            )
            return

        if self.core.call_success(PageText.page_has_text_by_url, doc_url, page_idx):
            self.notify_progress(
                ID,
                _(
                    "Document {doc_id} p{page_idx} has already some text."
                    " Not cropping."
                ).format(doc_id=doc_id, page_idx=(page_idx + 1)),
                page_nb=page_nb, total_pages=total_pages
            )
            return

        self.notify_progress(
            ID,
            _(
                "Using calibration to crop page borders of"
                " document {doc_id} p{page_idx}"
            ).format(doc_id=doc_id, page_idx=(page_idx + 1)),
            page_nb=page_nb, total_pages=total_pages
        )
        self.plugin.crop_page_borders_by_url(doc_url, page_idx)

    def _crop_new_pages(self, doc_id):
        doc_url = self.core.call_success(DocStorage.doc_id_to_url, doc_id)

        modified_pages = list(self.page_tracker.find_changes(doc_id, doc_url))

        for (page_nb, (change, page_idx)) in enumerate(modified_pages):
            # Guess page borders on new pages, but only if we are
            # not currently synchronizing with the work directory
            # (when syncing we don't modify the documents, ever)
            if not self.sync and change == 'new':
                self._crop_page(
                    doc_id, doc_url, page_idx, page_nb, len(modified_pages)
                )
            self.page_tracker.ack_page(doc_id, doc_url, page_idx)

    def add_doc(self, doc_id):
        self._crop_new_pages(doc_id)
        super().add_doc(doc_id)

    def upd_doc(self, doc_id):
        self._crop_new_pages(doc_id)
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


class Plugin(
    openpaperwork_core.PluginBase,
    Cropping,
    PredefinedCropping,
):
    PRIORITY = 4000

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': Config,
                'defaults': ['openpaperwork_core.config'],
            },
            {
                "interface": DocStorage,
                "defaults": ["paperwork_backend.model.workdir"],
            },
            {
                'interface': DocTracker,
                'defaults': ['paperwork_backend.sync.doctracker'],
            },
            {
                "interface": Mainloop,
                "defaults": ["openpaperwork_gtk.mainloop.glib"],
            },
            {
                "interface": PageImg,
                "defaults": [
                    "paperwork_backend.model.img",
                    "paperwork_backend.model.pdf",
                ],
            },
            {
                "interface": PageModificationListener,
                "defaults": [],
                "optional": True,
            },
            {
                "interface": PageText,
                "defaults": [
                    "paperwork_backend.model.hocr",
                    "paperwork_backend.model.pdf",
                ],
            },
            {
                'interface': PageTracker,
                'defaults': ['paperwork_backend.sync.pagetracker'],
            },
            {
                'interface': Pillow,
                'defaults': [
                    'openpaperwork_core.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ]
            },
            {
                "interface": ProgressListener,
                "defaults": [],
                "optional": True,
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.core.call_all(
            Config.config_register, "scanner_calibration",
            self.core.call_success(
                Config.config_build_simple, "scanner", "calibration",
                lambda: None
            )
        )
        self.core.call_all(
            DocTracker.doc_tracker_register, ID,
            lambda sync, total_expected=-1: CalibrationTransaction(
                self, sync, total_expected
            )
        )

    def crop_page_borders_by_url(self, doc_url, page_idx):
        frame = self.core.call_success(
            Config.config_get, "scanner_calibration"
        )
        if frame is None:
            LOGGER.warning(
                "No calibration found. Cannot crop page %s p%d",
                doc_url, page_idx
            )
            return None

        LOGGER.info(
            "Cropping page %d of %s (calibration=%s)",
            page_idx, doc_url, frame
        )

        doc_id = self.core.call_success(DocStorage.doc_url_to_id, doc_url)

        if doc_id is not None:
            self.core.call_one(
                Mainloop.mainloop_schedule, self.core.call_all,
                PageModificationListener.on_page_modification_start, doc_id, page_idx
            )
        try:
            page_img_url = self.core.call_success(
                PageImg.page_get_img_url, doc_url, page_idx
            )

            img = self.core.call_success(Pillow.url_to_pillow, page_img_url)

            LOGGER.info(
                "Cropping page %d of %s at %s", page_idx, doc_url, frame
            )
            # make sure we don't extend the image
            frame = (
                max(0, frame[0]),
                max(0, frame[1]),
                min(img.size[0], frame[2]),
                min(img.size[1], frame[3]),
            )
            img = img.crop(frame)

            page_img_url = self.core.call_success(
                PageImg.page_get_img_url, doc_url, page_idx, write=True
            )
            self.core.call_success(Pillow.pillow_to_url, img, page_img_url)
        finally:
            if doc_id is not None:
                self.core.call_one(
                    Mainloop.mainloop_schedule, self.core.call_all,
                    PageModificationListener.on_page_modification_end, doc_id, page_idx
                )
        return frame
