#!/usr/bin/python3

import logging
import time

import PIL.Image

import openpaperwork_core
import openpaperwork_core.promise

from . import util


THUMBNAIL_WIDTH = 64
THUMBNAIL_HEIGHT = 80

PAGE_THUMBNAIL_FILENAME = 'paper.{}.thumb.jpg'

LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 5000  # see page_get_img_url()

    def get_interfaces(self):
        return [
            'pages',
            'thumbnail',  # thumbnail_get_path()
            'thumbnailer',  # thumbnail_from_img()
        ]

    def get_deps(self):
        return [
            {
                'interface': 'page_img',
                'defaults': [
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.pdf',
                ],
            },
            {
                'interface': 'pillow',
                'defaults': [
                    'openpaperwork_core.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ],
            },
            {
                'interface': 'pillow_util',
                'defaults': ['openpaperwork_core.pillow.util'],
            },
            {
                'interface': 'thread',
                'defaults': ['openpaperwork_core.thread.simple'],
            },
        ]

    def thumbnail_get_doc(self, doc_url):
        return self.thumbnail_get_page(doc_url, page_idx=0)

    def thumbnail_get_doc_promise(self, doc_url):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.thumbnail_get_doc, args=(doc_url,)
        )

    def thumbnail_from_img(self, img):
        (width, height) = img.size
        scale = max(
            float(width) / THUMBNAIL_WIDTH,
            float(height) / THUMBNAIL_HEIGHT
        )
        width /= scale
        height /= scale
        width = max(width, 1)
        height = max(height, 1)
        return img.resize(
            (int(width), int(height)),
            getattr(PIL.Image, 'Resampling', PIL.Image).LANCZOS
        )

    def thumbnail_get_page(self, doc_url, page_idx):
        thumbnail_url = self.core.call_success(
            "fs_join", doc_url, PAGE_THUMBNAIL_FILENAME.format(page_idx + 1)
        )
        page_url = self.core.call_success(
            "page_get_img_url", doc_url, page_idx
        )
        if page_url is None:
            LOGGER.warning(
                "Failed to get thumbnail for %s p%d. No page URL",
                doc_url, page_idx
            )
            return None

        if self.core.call_success("fs_exists", thumbnail_url) is not None:
            thumbnail_mtime = self.core.call_success(
                "fs_get_mtime", thumbnail_url
            )
            if not self.core.call_success("fs_iswritable", thumbnail_url):
                page_mtime = self.core.call_success("fs_get_mtime", page_url)
                if thumbnail_mtime < page_mtime:
                    self.core.call_success("fs_unlink", thumbnail_url)

        if self.core.call_success("fs_exists", thumbnail_url) is not None:
            LOGGER.debug("Loading thumbnail for %s page %d", doc_url, page_idx)
            try:
                thumbnail = self.core.call_success(
                    "url_to_pillow", thumbnail_url
                )
                size = thumbnail.size
                if size[0] == THUMBNAIL_WIDTH or size[1] == THUMBNAIL_HEIGHT:
                    return thumbnail
                LOGGER.info(
                    "Thumbnail for %s page %d doesn't have the expected size"
                    " (%s instead of %s). Regenerating.",
                    doc_url, page_idx, size,
                    (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)
                )
            except Exception as exc:
                LOGGER.warning(
                    "Failed to load thumbnail for %s page %d. Regenerating",
                    doc_url, page_idx, exc_info=exc
                )

        LOGGER.info("Generating thumbnail for %s page %d", doc_url, page_idx)
        start = time.time()
        try:
            page = self.core.call_success("url_to_pillow", page_url)
        except Exception as exc:
            LOGGER.error("Failed to load page %s", page_url, exc_info=exc)
            page = self.core.call_success("pillow_get_error", "invalid")

        thumbnail = self.thumbnail_from_img(page)

        self.core.call_success(
            "pillow_to_url", thumbnail, thumbnail_url,
            format='JPEG', quality=0.85
        )

        stop = time.time()
        LOGGER.info(
            "Thumbnail for %s page %d generated in %f seconds",
            doc_url, page_idx, stop - start
        )
        return thumbnail

    def thumbnail_get_page_promise(self, doc_url, page_idx):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.thumbnail_get_page, args=(doc_url, page_idx)
        )

    def page_delete_by_url(self, doc_url, page_idx):
        return util.delete_page_file(
            self.core, PAGE_THUMBNAIL_FILENAME, doc_url, page_idx,
            trash=False
        )

    def page_move_by_url(
                self,
                source_doc_url, source_page_idx,
                dest_doc_url, dest_page_idx
            ):
        return util.move_page_file(
            self.core, PAGE_THUMBNAIL_FILENAME,
            source_doc_url, source_page_idx,
            dest_doc_url, dest_page_idx
        )

    def page_reset_by_url(self, doc_url, page_idx):
        # see model.img_overlay.page_reset_by_url()
        # We must force a rebuild of the thumbnail
        self.page_delete_by_url(doc_url, page_idx)

    def page_get_img_url(self, doc_url, page_idx, write=False, **kwargs):
        if not write:
            return None
        # Image is going to be updated --> We must force a rebuild of the
        # thumbnail
        self.page_delete_by_url(doc_url, page_idx)
        return None
