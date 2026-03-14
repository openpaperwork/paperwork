import datetime
import logging

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.mainloop import Mainloop
import openpaperwork_core
import openpaperwork_core.promise

from paperwork_backend.interfaces.doc_labels import DocLabels
from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_transactions import DocTransactionFactory
from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.sync import Syncable
import paperwork_backend.sync

from paperwork_gtk.interfaces.help import HelpDocs


LOGGER = logging.getLogger(__name__)

DOC_ID = "help_intro"


class Plugin(
    openpaperwork_core.PluginBase,
    DocLabels,
    DocStorage,
    DocTransactionFactory,
    Syncable,
):
    PRIORITY = -100000  # see storage_get_all_docs()

    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=["openpaperwork_gtk.fs.gio"],
            ),
            openpaperwork_core.Dependency(
                interface=HelpDocs,
                defaults=['paperwork_gtk.model.help'],
            ),
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=["openpaperwork_gtk.mainloop.glib"],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.doc_url = None
        self.thumbnail_url = None
        self.opened = False
        self.deleted = False

    def storage_get_all_docs(self, out: list, only_valid=True):
        if self.deleted or len(out) > 0:
            self.doc_url = None
            return

        self.doc_url = self.core.call_success(DocStorage.doc_id_to_url, DOC_ID)
        if (self.doc_url is None or
                not self.core.call_success(Fs.fs_exists, self.doc_url)):
            LOGGER.error(
                "Introduction document %s not found."
                " Was Paperwork packaged correctly ?",
                DOC_ID
            )
            self.doc_url = None
            return

        out.append((DOC_ID, self.doc_url))

    def labels_get_all(self, out: set):
        if self.doc_url is not None:
            self.core.call_all(HelpDocs.help_labels_get_all, out)

    def storage_delete_doc_id(self, doc_id, trash=True):
        if doc_id != DOC_ID:
            return
        self.doc_url = None
        self.deleted = True

    def _fake_delete_doc(self):
        if self.doc_url is None:
            return

        all_docs = []
        self.core.call_all(DocStorage.storage_get_all_docs, all_docs)
        all_docs = [doc for doc in all_docs if doc[0] != DOC_ID]

        if len(all_docs) <= 0:
            return

        self.deleted = True
        # make sure the index is up-to-date
        self.core.call_success(
            DocTransactionManager.transaction_simple, [("del", DOC_ID),]
        )

    def doc_transaction_start(self, out: list, total_expected=-1):
        class FakeDeleteDocTransaction(paperwork_backend.sync.BaseTransaction):
            priority = -100000

            def commit(s):
                if self.doc_url is None:
                    return
                self._fake_delete_doc()

        out.append(FakeDeleteDocTransaction(self.core, total_expected))

    def sync(self, promises: list):
        if self.doc_url is None:
            return
        promises.append(openpaperwork_core.promise.Promise(
            self.core, self._fake_delete_doc
        ))

    @openpaperwork_core.noop
    def doc_storage_get_name(self):
        pass

    @openpaperwork_core.noop
    def doc_has_labels_by_url(self, doc_url):
        pass

    @openpaperwork_core.noop
    def doc_get_labels_by_url(self, out: set, doc_url):
        pass

    @openpaperwork_core.noop
    def doc_get_labels_by_url_promise(self, out: list, doc_url):
        pass

    @openpaperwork_core.noop
    def doc_add_label_by_url(self, doc_url, label, color=None):
        pass

    @openpaperwork_core.noop
    def doc_remove_label_by_url(self, doc_url, label):
        pass

    @openpaperwork_core.noop
    def label_load_all(self, promises: list):
        pass

    @openpaperwork_core.noop
    def doc_id_to_url(self, doc_id, existing=True):
        pass

    @openpaperwork_core.noop
    def doc_url_to_id(self, doc_url):
        pass

    @openpaperwork_core.noop
    def doc_get_date_by_id(self, doc_id):
        pass

    @openpaperwork_core.noop
    def doc_get_id_by_date(self, date):
        pass

    @openpaperwork_core.noop
    def storage_get_id(self):
        pass

    @openpaperwork_core.noop
    def storage_get_new_doc(self, now_func=datetime.datetime.now):
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
