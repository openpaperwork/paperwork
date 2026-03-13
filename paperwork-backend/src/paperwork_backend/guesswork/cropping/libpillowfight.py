"""
Automatic page cropping using libpillowfight.find_scan_borders().
May or may not work.
"""
import logging

from openpaperwork_core.interfaces.progress import ProgressListener
import pillowfight

from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.pillow import Pillow
import openpaperwork_core

from paperwork_backend import (_, sync)
from paperwork_backend.guesswork.cropping import ID
from paperwork_backend.interfaces.cropping import Cropping
from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.page_modification import PageModificationListener
from paperwork_backend.interfaces.pages import PageImg
from paperwork_backend.interfaces.sync import DocTracker
from paperwork_backend.interfaces.sync import PageTracker


LOGGER = logging.getLogger(__name__)


class PillowfightTransaction(sync.BaseTransaction):
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

    def _guess_page_borders(
            self, doc_id, doc_url, page_idx, page_nb, total_pages):
        paper_size = self.core.call_success(
            PageImg.page_get_paper_size_by_url, doc_url, page_idx
        )
        if paper_size is not None:
            # We don't want to guess page borders on PDF files since they
            # are usually already well-cropped. Also the page borders won't
            # appear in the document, so libpillowfight algorithm can only
            # fail.
            self.notify_progress(
                ID,
                _("Document {doc_id} p{page_idx} already cropped").format(
                    doc_id=doc_id, page_idx=(page_idx + 1)
                ),
                page_nb=page_nb, total_pages=total_pages
            )
            return

        self.notify_progress(
            ID, _(
                "Guessing page borders of"
                " document {doc_id} p{page_idx}"
            ).format(doc_id=doc_id, page_idx=(page_idx + 1)),
            page_nb=page_nb, total_pages=total_pages
        )
        self.plugin.crop_page_borders_by_url(doc_url, page_idx)

    def _guess_new_pages_borders(self, doc_id):
        doc_url = self.core.call_success(DocStorage.doc_id_to_url, doc_id)

        need_end_notification = False
        modified_pages = list(self.page_tracker.find_changes(doc_id, doc_url))
        for (page_nb, (change, page_idx)) in enumerate(modified_pages):
            # Guess page borders on new pages, but only if we are
            # not synchronizing with the work directory
            # (when syncing we don't modify the documents, ever)
            if not self.sync and change == 'new':
                self._guess_page_borders(
                    doc_id, doc_url, page_idx, page_nb, len(modified_pages)
                )
                need_end_notification = True
            self.page_tracker.ack_page(doc_id, doc_url, page_idx)

        if need_end_notification:
            self.notify_progress(
                ID, _("Guessing page borders"),
                page_nb=len(modified_pages), total_pages=len(modified_pages)
            )

    def add_doc(self, doc_id):
        self._guess_new_pages_borders(doc_id)
        super().add_doc(doc_id)

    def upd_doc(self, doc_id):
        self._guess_new_pages_borders(doc_id)
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
):
    PRIORITY = 4000

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=DocStorage,
                defaults=["paperwork_backend.model.workdir"],
            ),
            openpaperwork_core.Dependency(
                interface=DocTracker,
                defaults=['paperwork_backend.sync.doctracker'],
            ),
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=["openpaperwork_gtk.mainloop.glib"],
            ),
            openpaperwork_core.Dependency(
                interface=PageImg,
                defaults=[
                    "paperwork_backend.model.img",
                    "paperwork_backend.model.pdf",
                ],
            ),
            openpaperwork_core.Dependency(
                interface=PageModificationListener,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=PageTracker,
                defaults=['paperwork_backend.sync.pagetracker'],
            ),
            openpaperwork_core.Dependency(
                interface=Pillow,
                defaults=[
                    'openpaperwork_core.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ]
            ),
            openpaperwork_core.Dependency(
                interface=ProgressListener,
                defaults=[],
                optional=True,
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.core.call_all(
            DocTracker.doc_tracker_register, ID,
            lambda sync, total_expected=-1: PillowfightTransaction(
                self, sync, total_expected
            )
        )

    def crop_page_borders_by_url(self, doc_url, page_idx):
        LOGGER.info("Cropping page %d of %s", page_idx, doc_url)

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

            frame = pillowfight.find_scan_borders(img)
            if frame[0] >= frame[2] or frame[1] >= frame[3]:
                LOGGER.warning(
                    "Invalid frame found for page %d of %s: %s. Cannot"
                    " crop automatically", page_idx, doc_url, frame
                )
                return None

            LOGGER.info(
                "Cropping page %d of %s at %s", page_idx, doc_url, frame
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
