import logging

import PIL
import PIL.Image
import pyocr
import pyocr.builders

import openpaperwork_core

from ... import (_, sync)


LOGGER = logging.getLogger(__name__)
ID = "orientation_guesser"


class OrientationTransaction(sync.BaseTransaction):
    def __init__(self, plugin, sync, total_expected=-1):
        super().__init__(plugin.core, total_expected)
        self.priority = plugin.PRIORITY

        self.plugin = plugin
        self.sync = sync

        # for each document, we need to track on which pages we have already
        # guessed the orientation and on which page we didn't yet.
        self.page_tracker = self.core.call_success("page_tracker_get", ID)

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()

    def _guess_page_orientation(
            self, doc_id, doc_url, page_idx, page_nb, total_pages):
        if self.core.call_success(
                    "page_has_text_by_url", doc_url, page_idx
                ):
            self.notify_progress(
                ID,
                _(
                    "Document {doc_id} p{page_idx} has already some text."
                    " Not guessing page orientation."
                ).format(doc_id=doc_id, page_idx=(page_idx + 1)),
                page_nb=page_nb, total_pages=total_pages
            )
            return

        self.notify_progress(
            ID,
            _(
                "Guessing orientation of"
                " document {doc_id} p{page_idx}"
            ).format(doc_id=doc_id, page_idx=(page_idx + 1)),
            page_nb=page_nb, total_pages=total_pages
        )
        self.plugin.guess_page_orientation_by_url(doc_url, page_idx)

    def _guess_new_page_orientations(self, doc_id):
        doc_url = self.core.call_success("doc_id_to_url", doc_id)

        need_end_notification = False
        modified_pages = list(self.page_tracker.find_changes(doc_id, doc_url))
        for (page_nb, (change, page_idx)) in enumerate(modified_pages):
            # Guess page orientation on new pages, but only if we are
            # not synchronizing with the work directory
            if not self.sync and change == 'new':
                self._guess_page_orientation(
                    doc_id, doc_url, page_idx, page_nb, len(modified_pages)
                )
                need_end_notification = True
            self.page_tracker.ack_page(doc_id, doc_url, page_idx)

        if need_end_notification:
            self.notify_progress(
                ID, _("Guessing page orientation"),
                page_nb=len(modified_pages), total_pages=len(modified_pages)
            )

    def add_doc(self, doc_id):
        self._guess_new_page_orientations(doc_id)
        super().add_doc(doc_id)

    def upd_doc(self, doc_id):
        self._guess_new_page_orientations(doc_id)
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
    PRIORITY = 2000

    def get_interfaces(self):
        return [
            "orientation_guesser",
            "syncable",  # actually satisfied by the plugin 'doctracker'
        ]

    def get_deps(self):
        return [
            {
                'interface': 'doc_tracking',
                'defaults': ['paperwork_backend.doctracker']
            },
            {
                'interface': 'ocr_settings',
                'defaults': ['paperwork_backend.pyocr'],
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
            lambda sync, total_expected=-1: OrientationTransaction(
                self, sync, total_expected
            )
        )

    def guess_page_orientation_by_url(self, doc_url, page_idx):
        if self.core.call_success("ocr_is_enabled") is None:
            LOGGER.info("OCR is disabled")
            return

        LOGGER.info(
            "Using OCR to guess orientation of page %d of %s",
            page_idx, doc_url
        )

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

            for ocr_tool in pyocr.get_available_tools():
                LOGGER.info(
                    "Orientation guessing: Will use tool '%s'",
                    ocr_tool.get_name()
                )
                if ocr_tool.can_detect_orientation():
                    break
                LOGGER.warning(
                    "Orientation guessing: Tool '%s' cannot detect"
                    " orientation",
                    ocr_tool.get_name()
                )
            else:
                LOGGER.warning(
                    "Orientation guessing: No tool found able to detect"
                    " orientation"
                )
                return None

            ocr_langs = self.core.call_success("ocr_get_active_langs")

            img = self.core.call_success("url_to_pillow", page_img_url)

            try:
                r = ocr_tool.detect_orientation(img, lang="+".join(ocr_langs))
            except pyocr.PyocrException as exc:
                LOGGER.warning(
                    "Orientation guessing: Failed to guess orientation",
                    exc_info=exc
                )
                return None

            angle = r['angle']
            if angle == 0:
                return 0

            transform_enum = getattr(PIL.Image, 'Transpose', PIL.Image)
            t_angle = {
                90: transform_enum.ROTATE_90,
                180: transform_enum.ROTATE_180,
                270: transform_enum.ROTATE_270,
            }[angle]
            img = img.transpose(t_angle)

            page_img_url = self.core.call_success(
                "page_get_img_url", doc_url, page_idx, write=True
            )
            self.core.call_success("pillow_to_url", img, page_img_url)
        finally:
            if doc_id is not None:
                self.core.call_one(
                    "mainloop_schedule", self.core.call_all,
                    "on_page_modification_end", doc_id, page_idx
                )

        return angle
