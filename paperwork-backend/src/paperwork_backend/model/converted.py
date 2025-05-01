"""
Takes of various document format that are actually converted to PDF files
so Paperwork can read them quickly
"""
import logging
import threading
import time

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.quit import QuitListener
from openpaperwork_core.interfaces.progress import ProgressListener
import openpaperwork_core
import openpaperwork_core.promise

from paperwork_backend import _
from paperwork_backend.interfaces.doc_converted import DocConverted
from paperwork_backend.interfaces.doc_converter import DocConverter
from paperwork_backend.interfaces.doc_pdf import DocPdf
from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_storage import DocStorageCache
from paperwork_backend.interfaces.doc_transactions import DocTransactionFactory
from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.docs import DocHash
from paperwork_backend.interfaces.docs import DocOpener
from paperwork_backend.interfaces.pages import PageImg
from paperwork_backend.interfaces.sync import Syncable


LOGGER = logging.Logger(__name__)

__all__ = [
    "Plugin",
]


class MonitoringThread:
    def __init__(self, plugin, doc_url):
        self.plugin = plugin
        self.doc_url = doc_url
        self.running = True

        LOGGER.info("Starting monitoring of converted document %s", self.doc_url)
        thread = threading.Thread(target=self.run, name="doc_converted_monitoring")
        thread.start()

    def stop(self):
        self.running = False
        LOGGER.info("Stopping monitoring of converted document %s", self.doc_url)

    def run(self):
        while self.running:
            time.sleep(2)
            self.plugin.doc_converted_check(self.doc_url)


class Plugin(
    openpaperwork_core.PluginBase,
    DocConverted,
    DocHash,
    DocOpener,
    PageImg,
    QuitListener,
    Syncable,
):
    PRIORITY = 200

    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            {
                'interface': DocConverter,
                'defaults': ['paperwork_backend.converter.libreoffice'],
            },
            {
                'interface': DocPdf,
                'defaults': ['paperwork_backend.model.pdf'],
            },
            {
                'interface': DocStorage,
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                "interface": DocStorageCache,
                "defaults": [
                    "paperwork_backend.model.pdf",
                    "paperwork_backend.model.img",
                ]
            },
            {
                "interface": DocTransactionFactory,
                "defaults": [],
                "optional": True,
            },
            {
                'interface': DocTransactionManager,
                'defaults': ['paperwork_backend.sync'],
            },
            {
                'interface': Fs,
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                "interface": Mainloop,
                "defaults": ["openpaperwork_gtk.mainloop.glib"],
            },
            {
                "interface": ProgressListener,
                "defaults": [],
                "optional": True,
            },
        ]

    def __init__(self, core):
        super().__init__(core)

        self.pending_doc_urls = set()
        self.file_types_by_ext = {}
        self.file_types_by_mime = {}
        self.cache_hash = {}

        file_types = []
        self.core.call_all(DocConverter.converter_get_file_types, file_types)

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

        self.active_doc = None
        self.monitoring_thread = None

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)
        if self.monitoring_thread is not None:
            self.monitoring_thread.stop()
        if self.doc_is_converted(doc_url):
            self.monitoring_thread = MonitoringThread(self, doc_url)

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    def doc_close(self):
        self.active_doc = None
        if self.monitoring_thread is not None:
            self.monitoring_thread.stop()
        self.monitoring_thread = None

    def on_quit(self):
        self.doc_close()

    def doc_is_converted(self, doc_url):
        if not self.core.call_success(Fs.fs_isdir, doc_url):
            return None
        for doc_file_url in self.core.call_success(Fs.fs_listdir, doc_url):
            doc_filename = self.core.call_success(Fs.fs_basename, doc_file_url)
            if "." not in doc_filename:
                continue
            (doc_filename, doc_ext) = doc_filename.rsplit(".", 1)
            doc_filename = doc_filename.lower()
            doc_ext = doc_ext.lower()
            if doc_filename == "doc" and doc_ext in self.file_types_by_ext:
                return (doc_file_url, doc_ext)
        else:
            # not a converted document
            return None

    def _update_pdf(self, doc_id, doc_url, doc_file_url, doc_ext):
        LOGGER.debug(
            "Document %s: %s (%s)",
            doc_id, doc_file_url, self.file_types_by_ext[doc_ext]
        )
        doc_mtime = self.core.call_success(Fs.fs_get_mtime, doc_file_url)

        pdf = self.core.call_success(
            DocPdf.doc_get_pdf_url_by_url, doc_url, write=True
        )
        if not self.core.call_success(Fs.fs_exists, pdf):
            pdf_mtime = -1
        else:
            pdf_mtime = self.core.call_success(Fs.fs_get_mtime, pdf)

        if pdf_mtime >= doc_mtime:
            LOGGER.debug("Document %s: PDF is up-to-date")
            return False

        LOGGER.info(
            "Document %s: Updating PDF: %s --> %s",
            doc_id, doc_file_url, pdf
        )
        self.core.call_all(
            ProgressListener.on_progress, "converting", 0.0,
            _("Converting document %s to PDF ...") % self.core.call_success(
                Fs.fs_basename, doc_file_url
            )
        )
        self.core.call_success(
            DocConverter.convert_file_to_pdf,
            doc_file_url, self.file_types_by_ext[doc_ext],
            pdf
        )
        self.core.call_all(DocStorageCache.flush_doc_cache, doc_url)
        LOGGER.info("PDF updated")
        self.core.call_all(ProgressListener.on_progress, "converting", 1.0)
        return True

    def page_get_img_url(self, doc_url, page_idx, write=False, **kwargs):
        if page_idx != 0:
            return
        self.doc_converted_check(doc_url)

    @openpaperwork_core.noop
    def page_get_paper_size_by_url(self, doc_url, page_idx):
        pass

    def doc_converted_check(self, doc_url):
        # prevent double conversion
        if doc_url in self.pending_doc_urls:
            LOGGER.debug("Doc %s has already been checked", doc_url)
            return
        self.pending_doc_urls.add(doc_url)

        doc_info = self.doc_is_converted(doc_url)
        if doc_info is None:
            self.pending_doc_urls.remove(doc_url)
            return
        (doc_file_url, doc_ext) = doc_info

        doc_id = self.core.call_success(DocStorage.doc_url_to_id, doc_url)

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
            self.core.call_all(DocTransactionFactory.doc_transaction_start, transactions, 1)
            transactions.sort(key=lambda t: -t.priority)

            try:
                for transaction in transactions:
                    transaction.upd_doc(doc_id)
                for transaction in transactions:
                    transaction.commit()
            except Exception:
                for transaction in transactions:
                    transaction.cancel()

            if self.active_doc is not None and doc_url == self.active_doc[1]:
                self.core.call_one(
                    Mainloop.mainloop_schedule,
                    self.core.call_all,
                    DocOpener.doc_close
                )
                self.core.call_one(
                    Mainloop.mainloop_schedule,
                    self.core.call_all,
                    DocOpener.doc_open, doc_id, doc_url
                )

        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, do_transaction
        ))
        promise = promise.then(self.pending_doc_urls.remove, doc_url)
        self.core.call_success(DocTransactionManager.transaction_schedule, promise)

        return None

    def _check_all_docs(self):
        if len(self.file_types_by_ext) <= 0:
            LOGGER.info("No file converter available")
            return

        LOGGER.info("Checking all converted documents ...")

        all_docs = []
        self.core.call_all(DocStorage.storage_get_all_docs, all_docs, only_valid=False)

        self.pending_doc_urls.update((x[1] for x in all_docs))

        msg = _("Checking converted documents")
        self.core.call_all(ProgressListener.on_progress, "converted_check", 0.0, msg)
        total = len(all_docs)
        for (idx, (doc_id, doc_url)) in enumerate(all_docs):
            doc_info = self.doc_is_converted(doc_url)
            if doc_info is None:
                continue
            (doc_file_url, doc_ext) = doc_info
            self._update_pdf(doc_id, doc_url, doc_file_url, doc_ext)
            self.pending_doc_urls.remove(doc_url)
            if idx % 100 == 0:
                self.core.call_all(
                    ProgressListener.on_progress, "converted_check", idx / total, msg
                )
        self.core.call_all(ProgressListener.on_progress, "converted_check", 1.0)
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
            mime = self.core.call_success(Fs.fs_get_mime, file_url)
            if mime is not None:
                file_ext = self.file_types_by_mime[mime]
            else:
                LOGGER.error("Failed to figure out file type of '%s'", file_url)
                return (None, None)

        file_name = "doc." + file_ext
        (doc_id, doc_url) = self.core.call_success(DocStorage.storage_get_new_doc)
        dst_file_url = self.core.call_success(Fs.fs_join, doc_url, file_name)
        self.core.call_success(Fs.fs_mkdir_p, doc_url)
        try:
            self.core.call_success(Fs.fs_copy, file_url, dst_file_url)
            self._update_pdf(doc_id, doc_url, dst_file_url, file_ext)
            return (doc_id, doc_url)
        except Exception:
            self.core.call_success(Fs.fs_rm_rf, doc_url, trash=False)
            raise

    def doc_get_hash_by_url(self, doc_url):
        doc_info = self.doc_is_converted(doc_url)
        if doc_info is None:
            return None
        (doc_file_url, doc_ext) = doc_info
        if doc_url not in self.cache_hash:
            h = self.core.call_success(Fs.fs_hash, doc_file_url)
            self.cache_hash[doc_url] = h
        return self.cache_hash[doc_url]
