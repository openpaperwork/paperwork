"""
This plugin is an helper for other plugins. It provides an easy way to
detect deleted, modified or added documents when synchronizing with the work
directory.
"""

import datetime
import logging
import time

from openpaperwork_core.interfaces.data_versioning import DataVersioning
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.progress import ProgressListener
from openpaperwork_core.interfaces.quit import QuitListener
from openpaperwork_core.interfaces.sqlite import Sqlite
import openpaperwork_core

from paperwork_backend import _
from paperwork_backend.interfaces.data_dir_handler import DataDirHandler
from paperwork_backend.interfaces.data_dir_handler import DataDirListener
from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_transactions import DocTransactionFactory
from paperwork_backend.interfaces.docs import Docs
from paperwork_backend.interfaces.docs import DocText
from paperwork_backend.interfaces.sync import DocTracker
from paperwork_backend.interfaces.sync import Syncable
from paperwork_backend.interfaces.sync import SyncListener
import paperwork_backend.sync


LOGGER = logging.getLogger(__name__)

CREATE_TABLES = [
    (
        "CREATE TABLE IF NOT EXISTS documents ("
        " doc_id TEXT PRIMARY KEY,"
        " text TEXT NULL,"
        " mtime INTEGER NOT NULL"
        ")"
    ),
]

ID = "doctracker"


def diff_lists(list_old, list_new):
    """
    Returns a dictionary giving the differences between both lists.

    Objects in the list must have 2 attributes:
    - `key`
    - `extra`
    (see ComparableDoc for instance)

    `key` values identify each object in both lists.
    Comparisons are done on `key` + `extra`.

    `list_old` will be unrolled immediately.

    Arguments:
        `list_old` -- [a, b, c, ...]
        `list_new` -- [a, c_modified, d, ...]

    Returns:
        [
            ('same', a.key),
            ('del', b.key),
            ('upd', c.key),
            ('add', d.key),
        ]

        list_old + diff => list_new
    """
    list_old = {obj.key: obj for obj in list_old}
    examined_new = set()

    for obj_new in list_new:
        examined_new.add(obj_new.key)

        if obj_new.key not in list_old:
            yield ('added', obj_new.key)
            continue

        obj_old = list_old[obj_new.key]
        if obj_new.extra != obj_old.extra:
            yield ('updated', obj_new.key)
        else:
            yield ('unchanged', obj_new.key)

    for obj_old in list_old.values():
        if obj_old.key not in examined_new:
            yield ('deleted', obj_old.key)


class ComparableDoc:
    def __init__(self, core, doc_id, doc_url):
        self.core = core
        self.key = doc_id
        self.doc_url = doc_url

    def get_mtime(self):
        mtime = self.core.call_success(Docs.doc_get_mtime_by_url, self.doc_url)
        if mtime is None:
            mtime = 0
        return datetime.datetime.fromtimestamp(mtime)

    extra = property(get_mtime)


class DocDiff:
    """
    This object allows to compare mtimes progressively. It then calls
    the methods `add_doc`, `del_doc`, `upd_doc` and `commit` on the given
    transaction object.

    Useful to handle calls to 'sync' (see interface 'syncable').
    """
    def __init__(self, core, names, new_all, old_all, transactions):
        self.core = core
        self.names = names
        self.new_all = new_all
        self.old_all = old_all
        self.transactions = transactions
        self.diff_generator = None
        self.start = None
        self.nb_compared = 0

        self.work_dir_id = self.core.call_success(DocStorage.storage_get_id)

    def get_promise(self):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.run
        )

    def run(self):
        self.start = time.time()
        self.diff_generator = diff_lists(self.old_all, self.new_all)

        try:
            for (action, key) in self.diff_generator:

                current_work_dir = self.core.call_success(DocStorage.storage_get_id)
                if self.work_dir_id != current_work_dir:
                    LOGGER.warning(
                        "%s: Work directory has changed during sync."
                        " Cancelling transactions",
                        self.names
                    )
                    for transaction in self.transactions:
                        transaction.cancel()
                    return

                self.nb_compared += 1
                if action != 'unchanged':
                    LOGGER.info("Sync: %s, %s", action, key)
                    for name in self.names:
                        self.core.call_one(
                            Mainloop.mainloop_schedule, self.core.call_all,
                            SyncListener.on_sync, name, action, key
                        )
                if action == "added":
                    for transaction in self.transactions:
                        LOGGER.debug(
                            "transaction.add_doc<%s>(%s)",
                            transaction.add_doc, key
                        )
                        transaction.add_doc(key)
                elif action == "updated":
                    for transaction in self.transactions:
                        LOGGER.debug(
                            "transaction.upd_doc<%s>(%s)",
                            transaction.upd_doc, key
                        )
                        transaction.upd_doc(key)
                elif action == "deleted":
                    for transaction in self.transactions:
                        LOGGER.debug(
                            "transaction.del_doc<%s>(%s)",
                            transaction.del_doc, key
                        )
                        transaction.del_doc(key)
                else:
                    for transaction in self.transactions:
                        LOGGER.debug(
                            "transaction.unchanged_doc<%s>(%s)",
                            transaction.unchanged_doc, key
                        )
                        transaction.unchanged_doc(key)

            LOGGER.info("Sync: Committing ...")
            for transaction in self.transactions:
                transaction.commit()
            LOGGER.info("Sync: Committed")
            stop = time.time()
            LOGGER.info(
                "%s: Has compared %d objects in %.3fs",
                self.names, self.nb_compared, stop - self.start
            )
        except Exception as exc:
            LOGGER.error(
                "%s: Fail to sync. Cancelling transactions",
                self.names, exc_info=exc
            )
            for transaction in self.transactions:
                transaction.cancel()


class DocTrackerTransaction(paperwork_backend.sync.BaseTransaction):
    def __init__(self, plugin, total_expected=-1):
        super().__init__(plugin.core, total_expected)
        self.priority = -10000

        # This transaction uses its own SqlLite connection to avoid issues
        # when the user switches from one work directory to another while
        # a transaction is still running.
        self.sql = self.core.call_one(
            Sqlite.sqlite_execute,
            self.core.call_success,
            Sqlite.sqlite_open, plugin._sql_file
        )

        self.core.call_one(
            Sqlite.sqlite_execute, self.sql.execute, "BEGIN TRANSACTION"
        )

    def _get_actual_doc_data(self, doc_id, doc_url):
        if (
                    doc_url is not None
                    and self.core.call_success(Fs.fs_exists, doc_url)
                    is not None
                ):
            mtime = self.core.call_success(Docs.doc_get_mtime_by_url, doc_url)
            if mtime is None:
                mtime = 0

            doc_text = []
            self.core.call_all(DocText.doc_get_text_by_url, doc_text, doc_url)
            doc_text = "\n\n".join(doc_text)
        else:
            mtime = 0
            doc_text = None

        return {
            'mtime': mtime,
            'text': doc_text,
        }

    def add_doc(self, doc_id):
        self.notify_progress(ID, _("Document %s added") % (doc_id))
        self._upd_doc(doc_id)
        super().add_doc(doc_id)

    def upd_doc(self, doc_id):
        self.notify_progress(ID, _("Document %s updated") % (doc_id))
        self._upd_doc(doc_id)
        super().upd_doc(doc_id)

    def _upd_doc(self, doc_id):
        doc_url = self.core.call_success(DocStorage.doc_id_to_url, doc_id)
        actual = self._get_actual_doc_data(doc_id, doc_url)

        self.core.call_one(
            Sqlite.sqlite_execute, self.sql.execute,
            "INSERT OR REPLACE INTO documents (doc_id, text, mtime)"
            " VALUES (?, ?, ?)",
            (doc_id, actual['text'], actual['mtime'])
        )

    def del_doc(self, doc_id):
        self.notify_progress(ID, _("Document %s deleted") % (doc_id))
        self.core.call_one(
            Sqlite.sqlite_execute, self.sql.execute,
            "DELETE FROM documents WHERE doc_id = ?",
            (doc_id,)
        )
        super().del_doc(doc_id)

    def unchanged_doc(self, doc_id):
        self.notify_progress(
            ID, _("Examining document %s: unchanged") % (doc_id)
        )
        super().unchanged_doc(doc_id)

    def cancel(self):
        self.notify_progress(ID, _("Rolling back changes"))
        self.core.call_one(Sqlite.sqlite_execute, self.sql.execute, "ROLLBACK")
        self.core.call_one(Sqlite.sqlite_execute, self.sql.close)
        self.notify_done(ID)

    def commit(self):
        self.notify_progress(ID, _("Committing changes"))
        self.core.call_one(Sqlite.sqlite_execute, self.sql.execute, "COMMIT")
        self.core.call_one(Sqlite.sqlite_execute, self.sql.close)
        self.notify_done(ID)


class DbDoc:
    def __init__(self, result):
        self.key = result[0]
        self.extra = datetime.datetime.fromtimestamp(result[1])


class Plugin(
    openpaperwork_core.PluginBase,
    DataDirListener,
    DocTransactionFactory,
    Syncable,
    DocTracker,
    QuitListener,
):
    PRIORITY = 10000

    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            {
                'interface': DataDirHandler,
                'defaults': ['paperwork_backend.datadirhandler'],
            },
            {
                'interface': DataVersioning,
                'defaults': ['openpaperwork_core.data_versioning'],
            },
            {
                'interface': Docs,
                'defaults': ['paperwork_backend.model'],
            },
            {
                'interface': DocStorage,
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                "interface": DocText,
                "defaults": [
                    "paperwork_backend.model.hocr",
                    "paperwork_backend.model.pdf",
                ],
            },
            {
                'interface': Fs,
                'defaults': ['openpaperwork_gtk.fs.gio']
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
            {
                'interface': Sqlite,
                'defaults': ['openpaperwork_core.sqlite'],
            },
            {
                "interface": SyncListener,
                "defaults": [],
                "optional": True,
            },
        ]

    def __init__(self, core):
        super().__init__(core)

        self._sql = None
        self._sql_file = None
        self.transaction_factories = []

        self._init()

    def _init(self):
        paperwork_dir = self.core.call_success(
            DataDirHandler.data_dir_handler_get_individual_data_dir,
        )
        self._sql_file = self.core.call_success(
            Fs.fs_join, paperwork_dir, 'doc_tracking.db'
        )
        self._sql = self.core.call_one(
            Sqlite.sqlite_execute,
            self.core.call_success,
            Sqlite.sqlite_open, self._sql_file
        )
        for query in CREATE_TABLES:
            self.core.call_one(Sqlite.sqlite_execute, self._sql.execute, query)

    def on_quit(self):
        LOGGER.info("Closing doc tracker db ...")
        self.core.call_one(
            Sqlite.sqlite_execute,
            self.core.call_success,
            Sqlite.sqlite_close, self._sql
        )
        self._sql = None

    def on_data_dir_changed(self):
        self.on_quit()
        self._init()

    def doc_tracker_register(self, name, transaction_factory):
        self.transaction_factories.append((name, transaction_factory))

    def doc_tracker_get_all_doc_ids(self):
        doc_ids = self.core.call_one(
            Sqlite.sqlite_execute, self._sql.execute,
            "SELECT doc_id FROM documents"
        )
        doc_ids = self.core.call_one(
            Sqlite.sqlite_execute, list, doc_ids
        )
        return {doc_id[0] for doc_id in doc_ids}

    def doc_tracker_get_doc_text_by_id(self, doc_id):
        """
        Return the text of a document as last-known.
        This method is useful when a document is deleted: when a plugin
        is notified that a document has been deleted, it may still need its
        text. Since the document won't be available anymore, we pull its text
        from the database (for instance, for label guesser untraining)
        """
        text = self.core.call_one(
            Sqlite.sqlite_execute, self._sql.execute,
            "SELECT text FROM documents WHERE doc_id = ? LIMIT 1",
            (doc_id,)
        )
        text = self.core.call_one(
            Sqlite.sqlite_execute, list, text
        )
        if len(text) <= 0:
            return None
        return text[0][0]

    def doc_transaction_start(self, out: list, total_expected=-1):
        for (name, transaction_factory) in self.transaction_factories:
            out.append(transaction_factory(
                sync=False, total_expected=total_expected
            ))
        out.append(DocTrackerTransaction(self, total_expected))

    def sync(self, promises: list):
        storage_all_docs = []
        names = [t[0] for t in self.transaction_factories]
        names.append('doc_tracker')

        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self.core.call_all,
            args=(DocStorage.storage_get_all_docs, storage_all_docs,)
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(storage_all_docs.sort)

        promise = promise.then(self._sql.cursor)
        promise = promise.then(lambda cursor: (
            [
                ComparableDoc(self.core, doc[0], doc[1])
                for doc in storage_all_docs
            ],
            [
                DbDoc(r)
                for r in cursor.execute("SELECT doc_id, mtime FROM documents")
            ],
        ))
        promise = promise.then(lambda args: (
            *args,
            sorted([
                transaction_factory(
                    sync=True,
                    total_expected=max(len(storage_all_docs), len(args[1]))
                )
                for (name, transaction_factory) in self.transaction_factories
            ] + [
                DocTrackerTransaction(
                    self,
                    total_expected=max(len(storage_all_docs), len(args[1]))
                )
            ], key=lambda t: -1 * t.priority),
        ))
        promise = promise.then(lambda args: DocDiff(
            self.core, names, args[0], args[1], args[2]
        ))
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, lambda syncer: syncer.run()
        ))
        promises.append(promise)
