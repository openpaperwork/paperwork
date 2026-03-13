import logging

import openpaperwork_core

from paperwork_backend.interfaces.docs import Docs
from paperwork_backend.interfaces.docs import DocType
from paperwork_backend.interfaces.pages import Pages
from paperwork_backend.interfaces.pages import PageType


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Docs,
    Pages,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=DocType,
                defaults=[
                    "paperwork_backend.model.img",
                    "paperwork_backend.model.pdf",
                ],
            ),
            openpaperwork_core.Dependency(
                interface=PageType,
                defaults=[
                    "paperwork_backend.model.img",
                    "paperwork_backend.model.pdf",
                ],
            ),
        ]

    def doc_get_nb_pages_by_url(self, doc_url):
        out = []
        self.core.call_all(DocType.doc_internal_get_nb_pages_by_url, out, doc_url)
        r = max(out, default=0)
        if r == 0:
            return None
        return r

    def page_get_hash_by_url(self, doc_url, page_idx):
        out = []
        self.core.call_all(
            PageType.page_internal_get_hash_by_url, out, doc_url, page_idx
        )
        r = 0
        for h in out:
            r ^= h
        return r

    def doc_get_mtime_by_url(self, doc_url):
        out = []
        self.core.call_all(DocType.doc_internal_get_mtime_by_url, out, doc_url)
        return max(out, default=None)

    def page_get_mtime_by_url(self, doc_url, page_idx):
        out = []
        self.core.call_all(
            PageType.page_internal_get_mtime_by_url, out, doc_url, page_idx
        )
        return max(out, default=None)
