import datetime
import locale
import logging

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.pillow import Pillow
from openpaperwork_core.interfaces.resources import Resources
import openpaperwork_core
import openpaperwork_core.promise

from paperwork_backend.interfaces.doc_labels import DocLabels
from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.docs import DocExtraText
from paperwork_backend.interfaces.docs import DocOpener
from paperwork_backend.interfaces.pages import PageImg
from paperwork_backend.interfaces.pages import PageText
from paperwork_backend.model import Docs
import paperwork_backend.model.pdf

from paperwork_gtk import _
from paperwork_gtk.interfaces.help import HelpDocs


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    DocExtraText,
    DocLabels,
    Docs,
    DocStorage,
    DocTransactionManager,
    HelpDocs,
    PageImg,
    PageText,
):
    PRIORITY = 10000

    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            {
                'interface': Fs,
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                "interface": Mainloop,
                "defaults": ["openpaperwork_gtk.mainloop.glib"],
            },
            {
                'interface': Pillow,
                'defaults': [
                    'openpaperwork_core.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ],
            },
            {
                'interface': Resources,
                'defaults': ['openpaperwork_core.resources.setuptools'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.doc_urls_to_names_to_urls = {}
        self.doc_urls_to_names = {}

        # in case document is edited by user
        self.new_docs = []
        self.doc_urls_to_new_docs = {}

        self.thumbnails = {}
        # At this point, translations are not yet available
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
                Resources.resources_get_file, "paperwork_gtk.model.help.out", doc
            )
            if path_ctx is None:
                LOGGER.warning("No documentation '%s' found", doc)
            else:
                with path_ctx as path:
                    LOGGER.info("Documentation '%s': %s", doc, path)
                    url = self.core.call_success(Fs.fs_safe, path)
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
        (new_doc_id, new_doc_url) = self.core.call_success(DocStorage.get_new_doc)
        assert new_doc_url not in self.doc_urls_to_names
        self.doc_urls_to_new_docs[doc_url] = new_doc_url
        self.new_docs.append(new_doc_id)
        self.core.call_success(Fs.fs_mkdir_p, new_doc_url)
        self.core.call_success(
            Fs.fs_copy,
            doc_url,  # reminder: doc_url points directly to a PDF here
            self.core.call_success(
                Fs.fs_join,
                new_doc_url, paperwork_backend.model.pdf.PDF_FILENAME
            )
        )
        self.core.call_success(
            DocLabels.doc_add_label_by_url, new_doc_url, *self.label
        )
        self.core.call_success(
            Mainloop.mainloop_execute, self.core.call_all,
            DocOpener.doc_open, new_doc_id, new_doc_url
        )
        return new_doc_url

    def page_get_img_url(self, doc_url, page_idx, write=False, **kwargs):
        if doc_url not in self.doc_urls_to_names:
            return None
        doc_url = self._get_doc_url(doc_url, write)
        if doc_url in self.doc_urls_to_names:
            return None
        return self.core.call_success(
            PageImg.page_get_img_url, doc_url, page_idx,
            write=write, **kwargs
        )

    def page_set_boxes_by_url(self, doc_url, page_idx, *args, **kwargs):
        if doc_url not in self.doc_urls_to_names:
            return None
        doc_url = self._get_doc_url(doc_url, write=True)
        return self.core.call_success(
            PageText.page_set_boxes_by_url, doc_url, page_idx,
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
            DocLabels.doc_remove_label_by_url, doc_url, *args, **kwargs
        )

    def doc_add_label_by_url(self, doc_url, *args, **kwargs):
        if doc_url not in self.doc_urls_to_names:
            return None
        doc_url = self._get_doc_url(doc_url, write=True)
        return self.core.call_success(
            DocLabels.doc_add_label_by_url, doc_url, *args, **kwargs
        )

    def doc_set_extra_text_by_url(self, doc_url, *args, **kwargs):
        if doc_url not in self.doc_urls_to_names:
            return None
        doc_url = self._get_doc_url(doc_url, write=True)
        return self.core.call_success(
            DocExtraText.doc_set_extra_text_by_url, doc_url, *args, **kwargs
        )

    def help_labels_get_all(self, out: set):
        out.add(self.label)

    @openpaperwork_core.noop
    def doc_url_to_id(self, doc_url):
        pass

    @openpaperwork_core.noop
    def doc_get_id_by_date(self, date):
        pass

    @openpaperwork_core.noop
    def storage_get_id(self):
        pass

    @openpaperwork_core.noop
    def storage_get_all_docs(self, out: list, only_valid=True):
        pass

    @openpaperwork_core.noop
    def storage_get_new_doc(self, now_func=datetime.datetime.now):
        pass

    @openpaperwork_core.noop
    def storage_delete_doc_id(self, doc_id, trash=True):
        pass

    @openpaperwork_core.noop
    def doc_rename_by_url(self, src_doc_url, dst_doc_url):
        pass

    @openpaperwork_core.noop
    def doc_copy_by_url(self, src_doc_url):
        pass

    @openpaperwork_core.noop
    def doc_get_size_by_url(self, doc_url):
        pass

    @openpaperwork_core.noop
    def labels_get_all(self, out: set):
        pass

    @openpaperwork_core.noop
    def label_load_all(self, promises: list):
        pass

    @openpaperwork_core.noop
    def page_has_text_by_url(self, doc_url, page_idx):
        pass

    @openpaperwork_core.noop
    def page_get_text_by_url(self, doc_url, page_idx):
        pass

    @openpaperwork_core.noop
    def page_get_boxes_by_url(self, doc_url, page_idx):
        pass

    @openpaperwork_core.noop
    def page_get_paper_size_by_url(self, doc_url, page_idx):
        pass

    @openpaperwork_core.noop
    def transaction_schedule(self, promise):
        pass

    @openpaperwork_core.noop
    def transaction_simple(self, changes: list):
        pass

    @openpaperwork_core.noop
    def transaction_sync_all(self):
        pass

    @openpaperwork_core.noop
    def doc_get_extra_text_by_url(self, out: list, doc_url):
        pass

    @openpaperwork_core.noop
    def doc_get_nb_pages_by_url(self, doc_url):
        pass
