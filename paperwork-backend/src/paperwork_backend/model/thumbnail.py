#!/usr/bin/python3

import logging
import time

import PIL.Image

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.pillow import Pillow
from openpaperwork_core.interfaces.pillow import PillowUtil
import openpaperwork_core
import openpaperwork_core.promise

from paperwork_backend.interfaces.doc_thumbnail import DocThumbnail
from paperwork_backend.interfaces.doc_thumbnail import DocThumbnailer
from paperwork_backend.interfaces.pages import PageImg
from paperwork_backend.interfaces.pages import PageManagement
from paperwork_backend.model import util


THUMBNAIL_WIDTH = 64
THUMBNAIL_HEIGHT = 80

PAGE_THUMBNAIL_FILENAME = 'paper.{}.thumb.jpg'

LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    DocThumbnail,
    DocThumbnailer,
    PageImg,
    PageManagement,
):
    PRIORITY = 5000  # see page_get_img_url()

    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + util.get_deps() + [
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=["openpaperwork_gtk.fs.gio"],
            ),
            openpaperwork_core.Dependency(
                interface=Pillow,
                defaults=[
                    'openpaperwork_core.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ],
            ),
            openpaperwork_core.Dependency(
                interface=PillowUtil,
                defaults=['openpaperwork_core.pillow.util'],
            ),
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
            Fs.fs_join, doc_url, PAGE_THUMBNAIL_FILENAME.format(page_idx + 1)
        )
        page_url = self.core.call_success(
            PageImg.page_get_img_url, doc_url, page_idx
        )
        if page_url is None:
            LOGGER.warning(
                "Failed to get thumbnail for %s p%d. No page URL",
                doc_url, page_idx
            )
            return None

        if self.core.call_success(Fs.fs_exists, thumbnail_url) is not None:
            thumbnail_mtime = self.core.call_success(
                Fs.fs_get_mtime, thumbnail_url
            )
            if self.core.call_success(Fs.fs_iswritable, thumbnail_url) is not None:
                base_page_url = page_url
                if "#" in page_url:
                    (base_page_url, page_url) = page_url.split("#", 1)
                page_mtime = self.core.call_success(Fs.fs_get_mtime, base_page_url)
                if thumbnail_mtime < page_mtime:
                    LOGGER.info(
                        "Thumbnail %s is obsolete. Regenerating", thumbnail_url
                    )
                    self.core.call_success(Fs.fs_unlink, thumbnail_url, trash=False)

        if self.core.call_success(Fs.fs_exists, thumbnail_url):
            LOGGER.debug("Loading thumbnail for %s page %d", doc_url, page_idx)
            try:
                thumbnail = self.core.call_success(
                    Pillow.url_to_pillow, thumbnail_url
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
            page = self.core.call_success(Pillow.url_to_pillow, page_url)
        except Exception as exc:
            LOGGER.error("Failed to load page %s", page_url, exc_info=exc)
            page = self.core.call_success(PillowUtil.pillow_get_error, "invalid")

        if page is None:
            # WORKAROUND(Jflesch): unclear what causes this problem. There are
            # no other log
            LOGGER.error("Failed to generate thumbail for %s", doc_url)
            return None

        thumbnail = self.thumbnail_from_img(page)

        self.core.call_success(
            Pillow.pillow_to_url, thumbnail, thumbnail_url,
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

    @openpaperwork_core.noop
    def page_get_paper_size_by_url(self, doc_url, page_idx):
        pass
