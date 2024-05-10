"""
This plugin is an helper for other plugins. It provides an easy way to
detect deleted, modified or added documents when synchronizing with the work
directory.
"""

import datetime
import logging

import openpaperwork_core

from . import (_, sync)

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


class DocTrackerTransaction(sync.BaseTransaction):
    def __init__(self, plugin, total_expected=-1):
        super().__init__(plugin.core, total_expected)
        self.priority = -10000

        # This transaction uses its own SqlLite connection to avoid issues
        # when the user switches from one work directory to another while
        # a transaction is still running.
        self.sql = self.core.call_one(
            "sqlite_execute",
            self.core.call_success,
            "sqlite_open", plugin.sql_file
        )

        self.core.call_one(
            "sqlite_execute", self.sql.execute, "BEGIN TRANSACTION"
        )

    def _get_actual_doc_data(self, doc_id, doc_url):
        if (
                    doc_url is not None
                    and self.core.call_success("fs_exists", doc_url)
                    is not None
                ):
            mtime = self.core.call_success("doc_get_mtime_by_url", doc_url)
            if mtime is None:
                mtime = 0

            doc_text = []
            self.core.call_all("doc_get_text_by_url", doc_text, doc_url)
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
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        actual = self._get_actual_doc_data(doc_id, doc_url)

        self.core.call_one(
            "sqlite_execute", self.sql.execute,
            "INSERT OR REPLACE INTO documents (doc_id, text, mtime)"
            " VALUES (?, ?, ?)",
            (doc_id, actual['text'], actual['mtime'])
        )

    def del_doc(self, doc_id):
        self.notify_progress(ID, _("Document %s deleted") % (doc_id))
        self.core.call_one(
            "sqlite_execute", self.sql.execute,
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
        self.core.call_one("sqlite_execute", self.sql.execute, "ROLLBACK")
        self.core.call_one("sqlite_execute", self.sql.close)
        self.notify_done(ID)

    def commit(self):
        self.notify_progress(ID, _("Committing changes"))
        self.core.call_one("sqlite_execute", self.sql.execute, "COMMIT")
        self.core.call_one("sqlite_execute", self.sql.close)
        self.notify_done(ID)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000

    def __init__(self):
        self.sql = None
        self.transaction_factories = []

    def get_interfaces(self):
        return [
            'doc_tracking',
            'syncable',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'data_versioning',
                'defaults': ['openpaperwork_core.data_versioning'],
            },
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio']
            },
            {
                'interface': 'data_dir_handler',
                'defaults': ['paperwork_backend.datadirhandler'],
            },
            {
                'interface': 'sqlite',
                'defaults': ['openpaperwork_core.sqlite'],
            },
            {
                'interface': 'thread',
                'defaults': ['openpaperwork_core.thread.simple'],
            },
        ]

    def init(self, core):
        super().init(core)
        self._init()

    def _init(self):
        paperwork_dir = self.core.call_success(
            "data_dir_handler_get_individual_data_dir"
        )
        self.sql_file = self.core.call_success(
            "fs_join", paperwork_dir, 'doc_tracking.db'
        )
        self.sql = self.core.call_one(
            "sqlite_execute",
            self.core.call_success,
            "sqlite_open", self.sql_file
        )
        for query in CREATE_TABLES:
            self.core.call_one("sqlite_execute", self.sql.execute, query)

    def on_quit(self):
        LOGGER.info("Closing doc tracker db ...")
        self.core.call_one(
            "sqlite_execute",
            self.core.call_success,
            "sqlite_close", self.sql
        )
        self.sql = None

    def on_data_dir_changed(self):
        self.on_quit()
        self._init()

    def doc_tracker_register(self, name, transaction_factory):
        self.transaction_factories.append((name, transaction_factory))

    def doc_tracker_get_all_doc_ids(self):
        doc_ids = self.core.call_one(
            "sqlite_execute", self.sql.execute,
            "SELECT doc_id FROM documents"
        )
        doc_ids = self.core.call_one(
            "sqlite_execute", list, doc_ids
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
            "sqlite_execute", self.sql.execute,
            "SELECT text FROM documents WHERE doc_id = ? LIMIT 1",
            (doc_id,)
        )
        text = self.core.call_one(
            "sqlite_execute", list, text
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
            args=("storage_get_all_docs", storage_all_docs,)
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(storage_all_docs.sort)

        class DbDoc(object):
            def __init__(self, result):
                self.key = result[0]
                self.extra = datetime.datetime.fromtimestamp(result[1])

        promise = promise.then(self.sql.cursor)
        promise = promise.then(lambda cursor: (
            [
                sync.StorageDoc(self.core, doc[0], doc[1])
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
        promise = promise.then(lambda args: sync.Syncer(
            self.core, names, args[0], args[1], args[2]
        ))
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, lambda syncer: syncer.run()
        ))
        promises.append(promise)

    def tests_cleanup(self):
        self.sql.close()
