"""
Automatic page cropping using libpillowfight.find_scan_borders().
May or may not work.
"""
import logging

import pillowfight

import openpaperwork_core

from ... import (_, sync)


LOGGER = logging.getLogger(__name__)
ID = "color"


class PillowfightTransaction(sync.BaseTransaction):
    def __init__(self, plugin, sync, total_expected=-1):
        super().__init__(plugin.core, total_expected)

        self.priority = plugin.PRIORITY

        self.plugin = plugin
        self.sync = sync
        self.core = plugin.core

        # for each document, we need to track on which pages we have already
        # adjusted the color and on which page we didn't yet.
        self.page_tracker = self.core.call_success("page_tracker_get", ID)

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()

    def _adjust_page_colors(
            self, doc_id, doc_url, page_idx, page_nb, total_pages):
        paper_size = self.core.call_success(
            "page_get_paper_size_by_url", doc_url, page_idx
        )
        if paper_size is not None:
            # probably a PDF --> no need to adjust colors
            self.notify_progress(
                ID,
                _(
                    "Document {doc_id} p{page_idx} already correctly"
                    " colorized"
                ).format(
                    doc_id=doc_id, page_idx=(page_idx + 1)
                ),
                page_nb=page_nb, total_pages=total_pages
            )
            LOGGER.info(
                "Paper size for new page %d (document %s) is known."
                " --> Assuming we don't need to adjust colors",
                doc_id, page_idx
            )
            return

        self.notify_progress(
            ID,
            _("Adjusting colors of document {doc_id} p{page_idx}").format(
                doc_id=doc_id, page_idx=(page_idx + 1)
            ),
            page_nb=page_nb, total_pages=total_pages
        )
        self.plugin.adjust_page_colors_by_url(doc_url, page_idx)

    def _adjust_new_pages_colors(self, doc_id):
        doc_url = self.core.call_success("doc_id_to_url", doc_id)

        need_end_notification = False
        modified_pages = list(self.page_tracker.find_changes(doc_id, doc_url))
        for (page_nb, (change, page_idx)) in enumerate(modified_pages):
            # Adjust page colors on new pages, but only if we are
            # not synchronizing with the work directory
            if not self.sync and change == 'new':
                self._adjust_page_colors(
                    doc_id, doc_url, page_idx, page_nb, len(modified_pages)
                )
                need_end_notification = True
            self.page_tracker.ack_page(doc_id, doc_url, page_idx)

        if need_end_notification:
            self.notify_progress(
                ID, _("Adjusting colors of document"),
                page_nb=len(modified_pages), total_pages=len(modified_pages)
            )

    def add_doc(self, doc_id):
        self._adjust_new_pages_colors(doc_id)
        super().add_doc(doc_id)

    def upd_doc(self, doc_id):
        self._adjust_new_pages_colors(doc_id)
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
    PRIORITY = 3000

    def get_interfaces(self):
        return [
            "color",
            "syncable",  # actually satisfied by the plugin 'doctracker'
        ]

    def get_deps(self):
        return [
            {
                'interface': 'doc_tracking',
                'defaults': ['paperwork_backend.doctracker'],
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
            lambda sync, total_expected=-1: PillowfightTransaction(
                self, sync, total_expected
            )
        )

    def adjust_page_colors_by_url(self, doc_url, page_idx):
        LOGGER.info("Adjusting colors of page %d of %s", page_idx, doc_url)
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

            img = self.core.call_success("url_to_pillow", page_img_url)

            img = pillowfight.ace(img, samples=200)

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

        return img
