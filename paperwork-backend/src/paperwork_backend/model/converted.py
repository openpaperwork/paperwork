"""
Takes of various document format that are actually converted to PDF files
so Paperwork can read them quickly
"""
import logging

import openpaperwork_core
import openpaperwork_core.promise

from .. import _


LOGGER = logging.Logger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 200

    def __init__(self):
        super().__init__()
        self.pending_doc_urls = set()
        self.file_types_by_ext = {}
        self.file_types_by_mime = {}
        self.cache_hash = {}

    def get_interfaces(self):
        return [
            "doc_convert_and_import",
            "doc_hash",
            "sync",
        ]

    def get_deps(self):
        return [
            {
                'interface': 'doc_converter',
                'defaults': ['paperwork_backend.converter.libreoffice'],
            },
            {
                'interface': 'doc_pdf_import',
                'defaults': ['paperwork_backend.model.pdf'],
            },
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def init(self, core):
        super().init(core)

        file_types = []
        self.core.call_all("converter_get_file_types", file_types)

        self.file_types_by_ext = {}
        for (mime, ext, human_name) in file_types:  # order matters !
            if ext in self.file_types_by_ext:
                continue
            self.file_types_by_ext[ext] = mime

        self.file_types_by_mime = {}
        for (mime, ext, human_name) in file_types:  # order matters !
            if mime in self.file_types_by_ext:
                continue
            self.file_types_by_mime[mime] = ext

    def _is_converted(self, doc_url):
        if not self.core.call_success("fs_isdir", doc_url):
            return (None, None)
        for doc_file_url in self.core.call_success("fs_listdir", doc_url):
            doc_filename = self.core.call_success("fs_basename", doc_file_url)
            if "." not in doc_filename:
                continue
            (doc_filename, doc_ext) = doc_filename.rsplit(".", 1)
            doc_filename = doc_filename.lower()
            doc_ext = doc_ext.lower()
            if doc_filename == "doc" and doc_ext in self.file_types_by_ext:
                return (doc_file_url, doc_ext)
            return (None, None)
        else:
            # not a converted document
            return (None, None)

    def _update_pdf(self, doc_id, doc_url, doc_file_url, doc_ext):
        LOGGER.debug(
            "Document %s: %s (%s)",
            doc_id, doc_file_url, self.file_types_by_ext[doc_ext]
        )
        doc_mtime = self.core.call_success("fs_get_mtime", doc_file_url)

        pdf = self.core.call_success(
            "doc_get_pdf_url_by_url", doc_url, write=True
        )
        if not self.core.call_success("fs_exists", pdf):
            pdf_mtime = -1
        else:
            pdf_mtime = self.core.call_success("fs_get_mtime", pdf)

        if pdf_mtime >= doc_mtime:
            LOGGER.debug("Document %s: PDF is up-to-date")
            return False

        LOGGER.info(
            "Document %s: Updating PDF: %s --> %s",
            doc_id, doc_file_url, pdf
        )
        self.core.call_all(
            "on_progress", "converting", 0.0,
            _("Converting document %s to PDF ...") % self.core.call_success(
                "fs_basename", doc_file_url
            )
        )
        self.core.call_success(
            "convert_file_to_pdf",
            doc_file_url, self.file_types_by_ext[doc_ext],
            pdf
        )
        self.core.call_all("flush_doc_cache", doc_url)
        LOGGER.info("PDF updated")
        self.core.call_all("on_progress", "converting", 1.0)
        return True

    def page_get_img_url(self, doc_url, page_idx, write=False, **kwargs):
        if page_idx != 0:
            return
        # prevent double conversion
        if doc_url in self.pending_doc_urls:
            LOGGER.debug("Doc %s has already been checked", doc_url)
            return
        self.pending_doc_urls.add(doc_url)

        (doc_file_url, doc_ext) = self._is_converted(doc_url)
        if doc_file_url is None:
            self.pending_doc_urls.remove(doc_url)
            return

        doc_id = self.core.call_success("doc_url_to_id", doc_url)

        LOGGER.info("Checking conversion of document %s is up-to-date", doc_id)

        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self._update_pdf, args=(
                doc_id, doc_url, doc_file_url, doc_ext
            )
        )

        def do_transaction(has_changed):
            if not has_changed:
                return

            transactions = []
            self.core.call_all("doc_transaction_start", transactions, 1)
            transactions.sort(key=lambda t: -t.priority)

            try:
                for transaction in transactions:
                    transaction.del_doc(doc_id)
                for transaction in transactions:
                    transaction.commit()
            except Exception:
                for transaction in transactions:
                    transaction.cancel()

        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, do_transaction
        ))
        promise = promise.then(self.pending_doc_urls.remove, doc_url)
        self.core.call_success("transaction_schedule", promise)

        return None

    def _check_all_docs(self):
        if len(self.file_types_by_ext) <= 0:
            LOGGER.info("No file converter available")
            return

        LOGGER.info("Checking all converted documents ...")

        all_docs = []
        self.core.call_all("storage_get_all_docs", all_docs, only_valid=False)

        self.pending_doc_urls.update((x[1] for x in all_docs))

        msg = _("Checking converted documents")
        self.core.call_all("on_progress", "converted_check", 0.0, msg)
        total = len(all_docs)
        for (idx, (doc_id, doc_url)) in enumerate(all_docs):
            (doc_file_url, doc_ext) = self._is_converted(doc_url)
            if doc_file_url is None:
                continue
            self._update_pdf(doc_id, doc_url, doc_file_url, doc_ext)
            self.pending_doc_urls.remove(doc_url)
            if idx % 100 == 0:
                self.core.call_all(
                    "on_progress", "converted_check", idx / total, msg
                )
        self.core.call_all("on_progress", "converted_check", 1.0)
        LOGGER.info("All converted documents have been checked")

    def sync(self, promises: list):
        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self._check_all_docs
        )
        promises.insert(0, promise)

    def doc_convert_and_import(self, file_url):
        if "." in file_url:
            file_ext = file_url.rsplit(".", 1)[-1].lower()
        else:
            mime = self.core.call_success("fs_get_mime", file_url)
            if mime is not None:
                file_ext = self.file_types_by_mime[mime]
            else:
                LOGGER.error("Failed to figure out file type of '%s'", file_url)
                return (None, None)

        file_name = "doc." + file_ext
        (doc_id, doc_url) = self.core.call_success("storage_get_new_doc")
        dst_file_url = self.core.call_success("fs_join", doc_url, file_name)
        self.core.call_success("fs_mkdir_p", doc_url)
        try:
            self.core.call_success("fs_copy", file_url, dst_file_url)
            self._update_pdf(doc_id, doc_url, dst_file_url, file_ext)
            return (doc_id, doc_url)
        except Exception:
            self.core.call_success("fs_rm_rf", doc_url, trash=False)
            raise

    def doc_get_hash_by_url(self, doc_url):
        (doc_file_url, doc_ext) = self._is_converted(doc_url)
        if doc_file_url is None:
            return None
        if doc_url not in self.cache_hash:
            h = self.core.call_success("fs_hash", doc_file_url)
            self.cache_hash[doc_url] = h
        return self.cache_hash[doc_url]
