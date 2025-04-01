"""
Let other plugins replace a page image without actually smashing the original
image. Also provide a method to drop the modified version of a page and revert
to the original only.
"""

import logging
import re

import openpaperwork_core

from . import util


LOGGER = logging.getLogger(__name__)

PAGE_FILENAME_PNG_FMT = "paper.{}.edited.png"
PAGE_FILENAME_JPG_FMT = "paper.{}.edited.jpg"
PAGE_FILENAME_FMTS = [
    PAGE_FILENAME_PNG_FMT,
    PAGE_FILENAME_JPG_FMT,
]
PAGE_FILENAME_REGEX = re.compile(r"paper\.(\d+)\.edited.(jpg|png)")


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000  # must have a higher priority than model.img / model.pdf

    @classmethod
    def get_interfaces(cls):
        return [
            "page_img",
            "page_reset",
            'pages',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        setting = self.core.call_success(
            "config_build_simple", "model",
            "img_overlay_format", lambda: "PNG"
        )
        self.core.call_all(
            "config_register", "model_img_overlay_format", setting
        )

    def doc_internal_get_mtime_by_url(self, out: list, doc_url):
        mtime = util.get_doc_mtime(self.core, doc_url, PAGE_FILENAME_REGEX)
        if mtime is not None:
            out.append(mtime)

    def page_internal_get_mtime_by_url(self, out: list, doc_url, page_idx):
        for filename_fmt in PAGE_FILENAME_FMTS:
            mtime = util.get_page_mtime(
                self.core, doc_url, page_idx, filename_fmt
            )
            if mtime is not None:
                out.append(mtime)
                break

    def page_internal_get_hash_by_url(self, out: list, doc_url, page_idx):
        for filename_fmt in PAGE_FILENAME_FMTS:
            h = util.get_page_hash(
                self.core, doc_url, page_idx, filename_fmt)
            if h is not None:
                out.append(h)
                break

    def page_get_img_url(
                self, doc_url, page_idx, write=False, original=False,
                **kwargs
            ):
        if original:
            # caller want the URL of the original image, not the edited one
            return None

        for filename_fmt in PAGE_FILENAME_FMTS:
            page_url = self.core.call_success(
                "fs_join", doc_url, filename_fmt.format(page_idx + 1)
            )
            if self.core.call_success("fs_exists", page_url) is not None:
                return page_url

        if not write:
            return None

        # caller wants to modify or create a page
        # check if we already have an original image. If so, we return our
        # URL. Otherwise, we let the caller write the original image first.
        if self.core.call_success(
                    "page_get_img_url", doc_url, page_idx, write=False
                ) is not None:
            # has already an original page (or even an edited one)
            # --> return our URL
            img_fmt = self.core.call_success(
                "config_get", "model_img_overlay_format"
            )
            if img_fmt == "PNG":
                filename_fmt = PAGE_FILENAME_PNG_FMT
            else:
                filename_fmt = PAGE_FILENAME_JPG_FMT
            return self.core.call_success(
                "fs_join", doc_url, filename_fmt.format(page_idx + 1)
            )

        # let the caller write an original page (see model.img)
        return None

    def page_delete_by_url(self, doc_url, page_idx):
        r = None
        for filename_fmt in PAGE_FILENAME_FMTS:
            r = util.delete_page_file(
                self.core, filename_fmt, doc_url, page_idx
            ) or r
        return r

    def page_move_by_url(
                self,
                source_doc_url, source_page_idx,
                dest_doc_url, dest_page_idx
            ):
        r = None
        for filename_fmt in PAGE_FILENAME_FMTS:
            r = util.move_page_file(
                self.core, filename_fmt,
                source_doc_url, source_page_idx,
                dest_doc_url, dest_page_idx
            ) or r
        return r

    def page_reset_by_url(self, doc_url, page_idx):
        """
        Reset a page image to its original content. In other word, we simply
        delete the edited image so the original one takes over again
        (see model.img).
        """
        for filename_fmt in PAGE_FILENAME_FMTS:
            page_url = self.core.call_success(
                "fs_join", doc_url, filename_fmt.format(page_idx + 1)
            )
            if self.core.call_success("fs_exists", page_url):
                self.core.call_success("fs_unlink", page_url, trash=False)
