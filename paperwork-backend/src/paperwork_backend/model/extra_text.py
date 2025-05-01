#!/usr/bin/python3

import logging

from openpaperwork_core.interfaces.fs import Fs
import openpaperwork_core

from paperwork_backend.interfaces.docs import DocExtraText
from paperwork_backend.interfaces.docs import DocText
from paperwork_backend.interfaces.docs import DocType

EXTRA_TEXT_FILENAME = 'extra.txt'

LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    DocText,
    DocType,
    DocExtraText,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': Fs,
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
        ]

    def doc_internal_get_mtime_by_url(self, out: list, doc_url):
        extra_url = self.core.call_success(
            Fs.fs_join, doc_url, EXTRA_TEXT_FILENAME
        )
        if self.core.call_success(Fs.fs_exists, extra_url) is None:
            return
        out.append(self.core.call_success(Fs.fs_get_mtime, extra_url))

    @openpaperwork_core.noop
    def is_doc(self, doc_url):
        pass

    @openpaperwork_core.noop
    def doc_internal_get_nb_pages_by_url(self, out: list, doc_url):
        pass

    def doc_get_text_by_url(self, out: list, doc_url):
        self.doc_get_extra_text_by_url(out, doc_url)

    @openpaperwork_core.noop
    def doc_get_title_by_url(self, doc_url):
        pass

    def doc_get_extra_text_by_url(self, out: list, doc_url):
        extra_url = self.core.call_success(
            Fs.fs_join, doc_url, EXTRA_TEXT_FILENAME
        )
        if self.core.call_success(Fs.fs_exists, extra_url) is None:
            return
        with self.core.call_success(Fs.fs_open, extra_url, 'r') as fd:
            out.append(fd.read())

    def doc_set_extra_text_by_url(self, doc_url, text):
        if not self.core.call_success(Fs.fs_isdir, doc_url):
            # Can happen on integrated documentation PDF files
            LOGGER.warning(
                "%s is not a directory. Cannot set extra text",
                doc_url
            )
            return
        extra_url = self.core.call_success(
            Fs.fs_join, doc_url, EXTRA_TEXT_FILENAME
        )
        with self.core.call_success(Fs.fs_open, extra_url, 'w') as fd:
            fd.write(text)
