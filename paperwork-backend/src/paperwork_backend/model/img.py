import logging
import re

import openpaperwork_core

from . import util


LOGGER = logging.getLogger(__name__)

PAGE_FILENAME_PNG_FMT = "paper.{}.png"
PAGE_FILENAME_JPG_FMT = "paper.{}.jpg"
PAGE_FILENAME_FMTS = (
    PAGE_FILENAME_PNG_FMT,
    PAGE_FILENAME_JPG_FMT,
)
PAGE_FILENAME_REGEX = re.compile(
    r"paper\.(\d+)\.(jpg|png)", flags=re.IGNORECASE
)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    @classmethod
    def get_interfaces(cls):
        return [
            "doc_type",
            "page_img",
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
            {
                # to provide doc_get_nb_pages_by_url()
                'interface': 'nb_pages',
                'defaults': ['paperwork_backend.model'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        setting = self.core.call_success(
            "config_build_simple", "model",
            "img_format", lambda: "PNG"
        )
        self.core.call_all(
            "config_register", "model_img_format", setting
        )

    def is_doc(self, doc_url):
        for filename_fmt in PAGE_FILENAME_FMTS:
            page_url = self.core.call_success(
                "fs_join", doc_url, filename_fmt.format(1)
            )
            if self.core.call_success("fs_exists", page_url) is not None:
                return True
        return None

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
            h = util.get_page_hash(self.core, doc_url, page_idx, filename_fmt)
            if h is not None:
                out.append(h)
                break

    def doc_internal_get_nb_pages_by_url(self, out: list, doc_url):
        nb_pages = util.get_nb_pages(self.core, doc_url, PAGE_FILENAME_REGEX)
        if nb_pages is None:
            return
        out.append(nb_pages)

    def page_get_img_url(self, doc_url, page_idx, write=False, **kwargs):
        if write:
            self.core.call_success("fs_mkdir_p", doc_url)
        for filename_fmt in PAGE_FILENAME_FMTS:
            page_url = self.core.call_success(
                "fs_join", doc_url, filename_fmt.format(page_idx + 1)
            )
            if self.core.call_success("fs_exists", page_url) is not None:
                return page_url
        if write:
            img_fmt = self.core.call_success("config_get", "model_img_format")
            if img_fmt == "PNG":
                filename_fmt = PAGE_FILENAME_PNG_FMT
            else:
                filename_fmt = PAGE_FILENAME_JPG_FMT
            return self.core.call_success(
                "fs_join", doc_url, filename_fmt.format(page_idx + 1)
            )
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
