#!/usr/bin/python3

import logging

import openpaperwork_core

EXTRA_TEXT_FILENAME = 'extra.txt'

LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            "doc_text",
            "extra_text",
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
        ]

    def doc_internal_get_mtime_by_url(self, out: list, doc_url):
        extra_url = self.core.call_success(
            "fs_join", doc_url, EXTRA_TEXT_FILENAME
        )
        if self.core.call_success("fs_exists", extra_url) is None:
            return
        out.append(self.core.call_success("fs_get_mtime", extra_url))

    def doc_get_text_by_url(self, out: list, doc_url):
        self.doc_get_extra_text_by_url(out, doc_url)

    def doc_get_extra_text_by_url(self, out: list, doc_url):
        extra_url = self.core.call_success(
            "fs_join", doc_url, EXTRA_TEXT_FILENAME
        )
        if self.core.call_success("fs_exists", extra_url) is None:
            return
        with self.core.call_success("fs_open", extra_url, 'r') as fd:
            out.append(fd.read())

    def doc_set_extra_text_by_url(self, doc_url, text):
        if not self.core.call_success("fs_isdir", doc_url):
            # Can happen on integrated documentation PDF files
            LOGGER.warning(
                "%s is not a directory. Cannot set extra text",
                doc_url
            )
            return
        extra_url = self.core.call_success(
            "fs_join", doc_url, EXTRA_TEXT_FILENAME
        )
        with self.core.call_success("fs_open", extra_url, 'w') as fd:
            fd.write(text)
