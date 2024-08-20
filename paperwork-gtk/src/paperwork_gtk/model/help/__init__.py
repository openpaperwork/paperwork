import datetime
import locale
import logging

import openpaperwork_core
import openpaperwork_core.promise
import paperwork_backend.model.pdf

from ... import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000

    def __init__(self):
        super().__init__()
        self.doc_urls_to_names_to_urls = {}
        self.doc_urls_to_names = {}

        # in case document is edited by user
        self.new_docs = []
        self.doc_urls_to_new_docs = {}

        self.thumbnails = {}
        # At this point, translations are not yet available
        self.help_files = ()
        self.label = ()

    def get_interfaces(self):
        return [
            'doc_labels',
            'document_storage',
            'help_documents',
            'thumbnail',
        ]

    def get_deps(self):
        return [
            # Dependency not declared to avoid dependency loop
            # {
            #     'interface': 'new_doc',
            #     'defaults': ['paperwork_gtk.new_doc'],
            # },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'page_img',
                'defaults': ['paperwork_backend.model.pdf'],
            },
            {
                'interface': 'pillow',
                'defaults': [
                    'openpaperwork_core.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ],
            },
            {
                'interface': 'resources',
                'defaults': ['openpaperwork_core.resources.setuptools'],
            },
            {
                'interface': 'thumbnailer',
                'defaults': ['paperwork_backend.model.thumbnail'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.help_files = (
            (_("Introduction"), "intro"),
            (_("User manual"), "usage"),
        )
        self.label = (_("Documentation"), "#ffffffffffff")

    def help_get_files(self):
        return self.help_files

    def help_get_file(self, name):
        lang = "en"
        try:
            lang = locale.getdefaultlocale()[0]
            if lang is None:
                lang = "en"
                LOGGER.warning("Failed to get default locale !")
            else:
                lang = lang[:2]
                LOGGER.info("User language: %s", lang)
        except Exception as exc:
            LOGGER.error(
                "get_documentation(): Failed to figure out locale."
                " Will default to English",
                exc_info=exc
            )
        if lang == "en":
            docs = [name + '.pdf']
        else:
            docs = ['translated_{}_{}.pdf'.format(name, lang), name + ".pdf"]

        for doc in docs:
            path_ctx = self.core.call_success(
                "resources_get_file", "paperwork_gtk.model.help.out", doc
            )
            if path_ctx is None:
                LOGGER.warning("No documentation '%s' found", doc)
            else:
                with path_ctx as path:
                    LOGGER.info("Documentation '%s': %s", doc, path)
                    url = self.core.call_success("fs_safe", path)
                    self.doc_urls_to_names_to_urls[name] = url
                    self.doc_urls_to_names[url] = name
                return url
        LOGGER.error("Failed to find documentation '%s'", name)
        return None

    def doc_id_to_url(self, doc_id, existing=True):
        if not doc_id.startswith("help_"):
            return None
        name = doc_id[len("help_"):]
        return self.help_get_file(name)

    def doc_get_date_by_id(self, doc_id):
        if not doc_id.startswith("help_"):
            return None
        return datetime.datetime.now()

    def thumbnail_get_doc_promise(self, doc_url):
        if doc_url not in self.doc_urls_to_names:
            return None
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.thumbnail_get_doc, args=(doc_url,)
        )

    def thumbnail_get_doc(self, doc_url):
        return self.thumbnail_get_page(doc_url, page_idx=0)

    def thumbnail_get_page(self, doc_url, page_idx):
        if doc_url not in self.doc_urls_to_names:
            return None
        if page_idx != 0:
            return None

        if doc_url in self.thumbnails:
            url = self.thumbnais[doc_url]
            return self.core.call_success("url_to_pillow", url)

        page_url = self.core.call_success(
            "page_get_img_url", doc_url, page_idx
        )
        assert page_url is not None
        img = self.core.call_success("url_to_pillow", page_url)
        img = self.core.call_success("thumbnail_from_img", img)

        (self.thumbnail_url, fd) = self.core.call_success(
            "fs_mktemp", prefix="thumbnail_help_intro", suffix=".jpeg",
            mode="wb"
        )
        fd.close()
        self.core.call_success(
            "pillow_to_url", img, self.thumbnail_url,
            format='JPEG', quality=0.85
        )
        return img

    def _get_doc_url(self, doc_url, write=False):
        # HACK(Jflesch):
        # This document is read-only, but Paperwork doesn't really
        # support read-only documents.
        # --> discretely copy the document and switch to the new document.
        new_doc_url = self.doc_urls_to_new_docs.get(doc_url, None)
        if new_doc_url is not None:
            return new_doc_url
        if not write:
            return doc_url
        (new_doc_id, new_doc_url) = self.core.call_success("get_new_doc")
        assert new_doc_url not in self.doc_urls_to_names
        self.doc_urls_to_new_docs[doc_url] = new_doc_url
        self.new_docs.append(new_doc_id)
        self.core.call_success("fs_mkdir_p", new_doc_url)
        self.core.call_success(
            "fs_copy",
            doc_url,  # reminder: doc_url points directly to a PDF here
            self.core.call_success(
                "fs_join",
                new_doc_url, paperwork_backend.model.pdf.PDF_FILENAME
            )
        )
        self.core.call_success(
            "doc_add_label_by_url", new_doc_url, *self.label
        )
        self.core.call_success(
            "mainloop_execute", self.core.call_all,
            "doc_open", new_doc_id, new_doc_url
        )
        return new_doc_url

    def page_get_img_url(self, doc_url, page_idx, write=False, **kwargs):
        if doc_url not in self.doc_urls_to_names:
            return None
        doc_url = self._get_doc_url(doc_url, write)
        if doc_url in self.doc_urls_to_names:
            return None
        return self.core.call_success(
            "page_get_img_url", doc_url, page_idx,
            write=write, **kwargs
        )

    def page_set_boxes_by_url(self, doc_url, page_idx, *args, **kwargs):
        if doc_url not in self.doc_urls_to_names:
            return None
        doc_url = self._get_doc_url(doc_url, write=True)
        return self.core.call_success(
            "page_set_boxes_by_url", doc_url, page_idx,
            *args, **kwargs
        )

    def transaction_simple_promise(self, changes: list):
        for new_doc_id in self.new_docs:
            changes.append(('add', new_doc_id))
        self.new_docs = []

    def doc_get_mtime_by_url(self, doc_url):
        if doc_url not in self.doc_urls_to_names:
            return
        return datetime.datetime(year=1971, month=1, day=1).timestamp()

    def doc_has_labels_by_url(self, doc_url):
        if doc_url not in self.doc_urls_to_names:
            return None
        return True

    def doc_get_labels_by_url(self, out: set, doc_url):
        if doc_url not in self.doc_urls_to_names:
            return
        out.add(self.label)

    def doc_get_labels_by_url_promise(self, out: list, doc_url):
        if doc_url not in self.doc_urls_to_names:
            return

        def get_labels(labels=None):
            if labels is None:
                labels = set()
            labels.add(self.label)
            return labels

        promise = openpaperwork_core.promise.Promise(
            self.core, get_labels
        )
        out.append(promise)

    def doc_remove_label_by_url(self, doc_url, *args, **kwargs):
        if doc_url not in self.doc_urls_to_names:
            return None
        doc_url = self._get_doc_url(doc_url, write=True)
        return self.core.call_success(
            "doc_remove_label_by_url", doc_url, *args, **kwargs
        )

    def doc_add_label_by_url(self, doc_url, *args, **kwargs):
        if doc_url not in self.doc_urls_to_names:
            return None
        doc_url = self._get_doc_url(doc_url, write=True)
        return self.core.call_success(
            "doc_add_label_by_url", doc_url, *args, **kwargs
        )

    def doc_set_extra_text_by_url(self, doc_url, *args, **kwargs):
        if doc_url not in self.doc_urls_to_names:
            return None
        doc_url = self._get_doc_url(doc_url, write=True)
        return self.core.call_success(
            "doc_set_extra_text_by_url", doc_url, *args, **kwargs
        )

    def help_labels_get_all(self, out: set):
        out.add(self.label)
