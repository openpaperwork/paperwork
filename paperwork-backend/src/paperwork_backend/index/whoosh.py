import datetime
import logging
import time

import whoosh.fields
import whoosh.index
import whoosh.qparser
import whoosh.query
import whoosh.sorting

from openpaperwork_core.interfaces.data_versioning import DataVersioning
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.i18n import I18n
from openpaperwork_core.interfaces.mainloop import Mainloop
import openpaperwork_core
import openpaperwork_core.promise
import openpaperwork_core.util

from paperwork_backend import _
from paperwork_backend.interfaces.data_dir_handler import DataDirHandler
from paperwork_backend.interfaces.data_dir_handler import DataDirListener
from paperwork_backend.interfaces.doc_labels import DocLabels
from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_transactions import DocTransactionFactory
from paperwork_backend.interfaces.docs import Docs
from paperwork_backend.interfaces.docs import DocHash
from paperwork_backend.interfaces.docs import DocText
from paperwork_backend.interfaces.index import Index
from paperwork_backend.interfaces.index import IndexListener
from paperwork_backend.interfaces.suggestions import SuggestionProvider
from paperwork_backend.interfaces.sync import SyncListener, Syncable
import paperwork_backend.sync
import paperwork_backend.sync.doctracker


LOGGER = logging.getLogger(__name__)
ID = "index"

WHOOSH_SCHEMA = whoosh.fields.Schema(
    docid=whoosh.fields.ID(stored=True, unique=True, sortable=True),
    docfilehash=whoosh.fields.ID(),
    content=whoosh.fields.TEXT(spelling=True),
    label=whoosh.fields.KEYWORD(commas=True, scorable=True),
    date=whoosh.fields.DATETIME(sortable=True),
    last_read=whoosh.fields.DATETIME(stored=True),
)


class CustomFuzzySearch(whoosh.qparser.query.FuzzyTerm):
    def __init__(
                self, fieldname, text, boost=1.0, maxdist=1,
                prefixlength=0, constantscore=True
            ):
        whoosh.qparser.query.FuzzyTerm.__init__(
            self, fieldname, text, boost, maxdist,
            prefixlength, constantscore=True
        )


class WhooshTransaction(paperwork_backend.sync.BaseTransaction):
    """
    Transaction to apply on the index. Methods may be slow but they
    are thread-safe.
    """
    def __init__(self, plugin, total_expected=-1):
        super().__init__(plugin.core, total_expected)

        self.priority = plugin.PRIORITY

        LOGGER.debug("Starting Whoosh index transaction")
        self.core = plugin.core
        self.writer = None
        self.modified = 0

        self.writer = plugin.index.writer()

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()

    def __del__(self):
        self.cancel()

    def _update_doc_in_index(self, doc_id):
        """
        Collect infos on the document and add/update a document in the index
        """
        doc_url = self.core.call_success(DocStorage.doc_id_to_url, doc_id)

        doc_mtime = self.core.call_success(Docs.doc_get_mtime_by_url, doc_url)
        if doc_mtime is None:
            doc_mtime = 0
        doc_mtime = datetime.datetime.fromtimestamp(doc_mtime)

        doc_hash = self.core.call_success(DocHash.doc_get_hash_by_url, doc_url)
        if doc_hash is None:
            # we get a hash only for PDF documents, not image documents.
            doc_hash = "undefined"
        else:
            doc_hash = ("%X" % doc_hash)

        doc_text = []
        self.core.call_all(DocText.doc_get_text_by_url, doc_text, doc_url)
        doc_text = "\n\n".join(doc_text)
        doc_text = self.core.call_success(I18n.i18n_strip_accents, doc_text)

        doc_labels = set()
        self.core.call_all(DocLabels.doc_get_labels_by_url, doc_labels, doc_url)
        doc_labels = ",".join([label[0] for label in doc_labels])
        doc_labels = self.core.call_success(I18n.i18n_strip_accents, doc_labels)

        doc_date = self.core.call_success(DocStorage.doc_get_date_by_id, doc_id)
        if doc_date is None:
            doc_date = datetime.datetime(year=1970, month=1, day=1)

        query = whoosh.query.Term("docid", doc_id)
        self.writer.delete_by_query(query)

        self.writer.update_document(
            docid=doc_id,
            docfilehash=doc_hash,
            content=doc_text,
            label=doc_labels,
            date=doc_date,
            last_read=doc_mtime
        )

    def add_doc(self, doc_id):
        LOGGER.info("Adding document '%s' to index", doc_id)
        self.notify_progress(
            ID, _("Indexing new document %s") % doc_id
        )
        self._update_doc_in_index(doc_id)
        self.modified += 1
        super().add_doc(doc_id)

    def del_doc(self, doc_id):
        LOGGER.info("Removing document '%s' from index", doc_id)
        self.notify_progress(
            ID, _("Removing document %s from index") % doc_id
        )
        query = whoosh.query.Term("docid", doc_id)
        self.writer.delete_by_query(query)
        self.modified += 1
        super().del_doc(doc_id)

    def upd_doc(self, doc_id):
        LOGGER.info("Updating document '%s' in index", doc_id)
        self.notify_progress(
            ID, _("Indexing updated document %s") % doc_id
        )
        self._update_doc_in_index(doc_id)
        self.modified += 1
        super().upd_doc(doc_id)

    def unchanged_doc(self, doc_id):
        self.notify_progress(
            ID, _("Examining document %s: unchanged") % (doc_id)
        )
        super().unchanged_doc(doc_id)

    def cancel(self):
        if self.writer is None:
            return

        self.core.call_one(
            Mainloop.mainloop_schedule, self.core.call_all,
            IndexListener.on_index_cancel,
        )
        LOGGER.info("Canceling transaction")
        self.writer.cancel()
        self.writer = None
        self.core.call_one(
            Mainloop.mainloop_schedule, self.core.call_all,
            IndexListener.on_index_updated,
        )
        self.notify_done(ID)

    def commit(self):
        self.notify_progress(
            ID, _("Committing changes in the index ...")
        )
        self.core.call_one(
            Mainloop.mainloop_schedule, self.core.call_all,
            IndexListener.on_index_commit_start,
        )
        if self.modified <= 0:
            LOGGER.info(
                "commit() called but nothing to commit."
                " Cancelling transaction"
            )
            self.writer.cancel()
            self.writer = None
        else:
            LOGGER.info(
                "Committing %d changes to Whoosh index", self.modified
            )
            self.writer.commit()
            self.writer = None
        self.notify_done(ID)
        self.core.call_success(
            Mainloop.mainloop_schedule, self.core.call_all,
            IndexListener.on_index_commit_end,
        )


class Plugin(
    openpaperwork_core.PluginBase,
    DataDirListener,
    DocTransactionFactory,
    Index,
    Syncable,
    SuggestionProvider,
    metaclass=openpaperwork_core.util.Singleton
):
    @classmethod
    def get_deps(cls):
        return (
            openpaperwork_core.promise.get_deps()
            + paperwork_backend.sync.BaseTransaction.get_deps()
            + [
                openpaperwork_core.Dependency(
                    interface=DataDirHandler,
                    defaults=["paperwork_backend.datadirhandler"],
                ),
                openpaperwork_core.Dependency(
                    interface=DataVersioning,
                    defaults=['openpaperwork_core.data_versioning'],
                ),
                openpaperwork_core.Dependency(
                    interface=DocStorage,
                    defaults=['paperwork_backend.model.workdir'],
                ),
                openpaperwork_core.Dependency(
                    interface=DocLabels,
                    defaults=["paperwork_backend.model.labels"],
                ),
                openpaperwork_core.Dependency(
                    interface=DocHash,
                    defaults=["paperwork_backend.model.pdf"],
                ),
                openpaperwork_core.Dependency(
                    interface=Docs,
                    defaults=["paperwork_backend.model"],
                ),
                openpaperwork_core.Dependency(
                    interface=DocText,
                    defaults=[
                        "paperwork_backend.model.hocr",
                        "paperwork_backend.model.pdf",
                    ],
                ),
                openpaperwork_core.Dependency(
                    interface=Fs,
                    defaults=['openpaperwork_gtk.fs.gio'],
                ),
                openpaperwork_core.Dependency(
                    interface=I18n,
                    defaults=['openpaperwork_core.i18n.python'],
                ),
                openpaperwork_core.Dependency(
                    interface=IndexListener,
                    defaults=[],
                    optional=True,
                ),
                openpaperwork_core.Dependency(
                    interface=Mainloop,
                    defaults=['openpaperwork_gtk.mainloop.glib'],
                ),
                openpaperwork_core.Dependency(
                    interface=SyncListener,
                    defaults=[],
                    optional=True,
                ),
            ]
        )

    def __init__(self, core):
        super().__init__(core)
        self.obs_callbacks = []
        self.query_parsers = {
            'strict': [],
            'fuzzy': [],
        }
        self.index = None

        self.local_dir = None
        self.index_dir = None
        self._init()

    def _init(self):
        data_dir = self.core.call_success(
            DataDirHandler.data_dir_handler_get_individual_data_dir,
        )
        self.index_dir = self.core.call_success(
            Fs.fs_join, data_dir, "index"
        )

        need_index_rewrite = True
        while need_index_rewrite:
            try:
                LOGGER.info(
                    "Opening Whoosh index '%s' ...", self.index_dir
                )
                self.index = whoosh.index.open_dir(
                    self.core.call_success(Fs.fs_unsafe, self.index_dir)
                )
                # check that the schema is up-to-date
                # We use the string representation of the schemas, because
                # previous versions of whoosh don't always implement __eq__
                if str(self.index.schema) != str(WHOOSH_SCHEMA):
                    raise Exception("Index version mismatch")
                need_index_rewrite = False
            except Exception as exc:
                LOGGER.warning(
                    "Failed to open index '%s': %s."
                    " Will rebuild index from scratch",
                    self.index_dir, exc
                )

            if need_index_rewrite:
                self._destroy()

                LOGGER.info("Creating a new index")

                self.core.call_success(Fs.fs_mkdir_p, self.index_dir)

                new_index = whoosh.index.create_in(
                    self.core.call_success(Fs.fs_unsafe, self.index_dir),
                    WHOOSH_SCHEMA
                )
                new_index.close()
                LOGGER.info("Index '%s' created", self.index_dir)

        self.query_parsers = {
            'fuzzy': [
                whoosh.qparser.MultifieldParser(
                    ["label", "content"], schema=self.index.schema,
                    termclass=CustomFuzzySearch
                ),
                whoosh.qparser.MultifieldParser(
                    ["label", "content"], schema=self.index.schema,
                    termclass=whoosh.qparser.query.Prefix
                ),
            ],
            'strict': [
                whoosh.qparser.MultifieldParser(
                    ["label", "content"], schema=self.index.schema,
                    termclass=whoosh.query.Term
                ),
            ],
        }

    def on_data_dir_changed(self):
        self._close()
        self._init()

    def _close(self):
        LOGGER.info("Closing Whoosh index")
        if self.index is not None:
            self.index.close()
        self.index = None

    def _destroy(self):
        self._close()
        if self.core.call_success(Fs.fs_exists, self.index_dir) is not None:
            LOGGER.warning("Destroying the index ...")
            self.core.call_success(Fs.fs_rm_rf, self.index_dir)
            LOGGER.warning("Index destroyed")

    def doc_transaction_start(self, out: list, total_expected=-1):
        out.append(WhooshTransaction(self, total_expected))

    def index_search(self, out: list, query, limit=None, search_type='fuzzy'):
        start = time.time()

        out_set = set()

        query = query.strip()
        query = self.core.call_success(I18n.i18n_strip_accents, query)
        if query == "":
            queries = [whoosh.query.Every()]
        else:
            queries = []
            for parser in self.query_parsers[search_type]:
                queries.append(parser.parse(query))

        with self.index.searcher() as searcher:
            for q in queries:
                facet = whoosh.sorting.FieldFacet("docid", reverse=True)
                results = searcher.search(q, limit=limit, sortedby=facet)
                has_results = False
                for result in results:
                    has_results = True
                    doc_id = result['docid']
                    doc_url = self.core.call_success(DocStorage.doc_id_to_url, doc_id)
                    if doc_url is None:
                        continue
                    out_set.add((doc_id, doc_url))
                    if limit is not None and len(out_set) >= limit:
                        break
                if has_results:
                    break

        out += out_set

        stop = time.time()
        LOGGER.info(
            "Search [%s] took %dms (limit=%s, type=%s)",
            query, (stop - start) * 1000, limit, search_type
        )

    def index_get_doc_id_by_hash(self, doc_hash):
        doc_hash = "%X" % doc_hash
        with self.index.searcher() as searcher:
            results = searcher.search(
                whoosh.query.Term('docfilehash', doc_hash)
            )
            if len(results) <= 0:
                return None
            return results[0]

    def suggestion_get(self, out: set, sentence):
        query_parser = self.query_parsers['strict'][0]
        query = query_parser.parse(sentence)

        with self.index.searcher() as searcher:
            corrected = searcher.correct_query(
                query, sentence, correctors={
                    'content': searcher.corrector("content"),
                    'label': searcher.corrector("label"),
                }
            )
            if corrected.query != query:
                out.add(corrected.string)

    def sync(self, promises: list):
        """
        Requests the document list from the document storage plugin
        and updates the index accordingly.

        This call is asynchronous and use the main loop to do its job.
        """
        storage_all_docs = []

        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self.core.call_all,
            args=(DocStorage.storage_get_all_docs, storage_all_docs,)
        )
        promise = promise.then(lambda *args, **kwargs: None)

        class IndexDoc(object):
            def __init__(s, index_result):
                (s.key, s.extra) = index_result

        def get_index_docs():
            with self.index.searcher() as searcher:
                index_all_docs = searcher.search(
                    whoosh.query.Every(), limit=None
                )
                index_all_docs = [
                    (result['docid'], result['last_read'])
                    for result in index_all_docs
                ]
                index_all_docs = [IndexDoc(r) for r in index_all_docs]
            return index_all_docs

        promise = promise.then(
            lambda: (
                [
                    paperwork_backend.sync.doctracker.ComparableDoc(self.core, doc[0], doc[1])
                    for doc in storage_all_docs
                ],
                get_index_docs()
            )
        )
        promise = promise.then(
            lambda args: (
                args[0], args[1],
                [WhooshTransaction(
                    self, max(len(storage_all_docs), len(args[1]))
                )]
            )
        )
        promise = promise.then(lambda args: paperwork_backend.sync.doctracker.DocDiff(
            self.core, ["whoosh"], args[0], args[1], args[2]
        ))
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, lambda doc_diff: doc_diff.run()
        ))
        promises.append(promise)
