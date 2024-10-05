"""
Create an index database for OpenPaperView and expose it in the HTTPS server.
See https://github.com/bwt/OpenPaperView/blob/main/tools/create_viewer_cb.py
"""

from typing import Optional
import abc
import logging
import os
import re
import time
import threading

from paperwork_backend import _
import openpaperwork_core
import openpaperwork_core.promise
import openpaperwork_core.util
import paperwork_backend.http
import paperwork_backend.index
import paperwork_backend.sync
import paperwork_backend.sync.doctracker


QUERY_PATH = "/papers.sqlite"

ID = "openpaperview_index"

LOGGER = logging.getLogger(__name__)

DB_LOCK = threading.Lock()


class AbstractDbTable(abc.ABC):
    CREATE_TABLE_QUERIES = None

    @abc.abstractmethod
    def delete(self, core, db_cursor, doc_id, doc_url):
        ...

    @abc.abstractmethod
    def insert(self, core, db_cursor, doc_id, doc_url):
        ...

    def commit(self, core, db_cursor):
        pass


class DbTableDocument(AbstractDbTable):
    CREATE_TABLE_QUERIES = [
        (
            "CREATE TABLE IF NOT EXISTS Document ("
            " documentId INTEGER NOT NULL PRIMARY KEY,"
            " name TEXT NOT NULL,"
            " title TEXT NULL,"
            " thumb TEXT NULL,"
            " pageCount INTEGER NOT NULL,"
            " date INTEGER NOT NULL,"
            " mtime INTEGER NOT NULL,"
            " size INTEGER NOT NULL"
            ");"
        ),
        "CREATE INDEX IF NOT EXISTS Document_date on Document(date);",
    ]

    def __init__(self):
        self.doc_db_id = None

    def delete(self, core, db_cursor, doc_id, doc_url):
        core.call_one(
            "sqlite_execute", db_cursor.execute,
            "DELETE FROM Document WHERE name = ?",
            (doc_id,)
        )

    def insert(self, core, db_cursor, doc_id, doc_url):
        self.doc_db_id = None

        nb_pages = core.call_success("doc_get_nb_pages_by_url", doc_url) or 0
        if nb_pages <= 0:
            # very unlikely, but possible (a PDF with 0 nb_pages)
            LOGGER.warning("Document %s has no pages !?", doc_id)
            return

        extra_text = []
        core.call_success("doc_get_extra_text_by_url", extra_text, doc_url)
        extra_text = "\n".join(extra_text)

        if extra_text.startswith("#"):
            extra_text = extra_text.split("\n")
            title = extra_text[0]
            extra_text = "\n".join(extra_text[1:])
        else:
            title = core.call_success("doc_get_title_by_url", doc_url)
            if title is None:
                title = ""

        date = core.call_success("doc_get_date_by_id", doc_id)
        date = int(time.mktime(date.timetuple()) * 1000)

        mtime = core.call_success("doc_get_mtime_by_url", doc_url)

        size = core.call_success("doc_get_size_by_url", doc_url)

        core.call_one(
            "sqlite_execute", db_cursor.execute,
            "INSERT INTO Document (name, title, thumb, pageCount, date, mtime, size)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                doc_id,
                title,
                "paper.1.thumb.jpg",
                nb_pages,
                date,
                mtime,
                size,
            )
        )
        self.doc_db_id = db_cursor.lastrowid


class DbTablePart(AbstractDbTable):
    CREATE_TABLE_QUERIES = [
        (
            "CREATE TABLE IF NOT EXISTS Part ("
            " partId INTEGER NOT NULL PRIMARY KEY,"
            " documentId INTEGER NOT NULL,"
            " name TEXT NOT NULL,"
            " downloadStatus INTEGER NOT NULL DEFAULT 100,"
            " downloadError TEXT NULL,"
            " CONSTRAINT fkDocument"
            "  FOREIGN KEY (documentId)"
            "  REFERENCES Document(documentId)"
            "  ON DELETE CASCADE"
            ");"
        ),
        "CREATE INDEX IF NOT EXISTS Part_documentId on Part(documentId);",
        "CREATE INDEX IF NOT EXISTS Part_downloadStatus on Part(downloadStatus);",
    ]

    PART_WHITELIST = ["pdf", "png", "jpg", "jpeg"]

    def __init__(self, db_table_doc: DbTableDocument):
        self.db_table_doc = db_table_doc

    def delete(self, core, db_cursor, doc_id, doc_url):
        # Handled by "ON DELETE CASCADE"
        pass

    def _is_whitelisted(self, file_name):
        if ".thumb." in file_name:
            return False
        ext = file_name.rsplit(".", 1)[-1]
        return ext.lower() in self.PART_WHITELIST

    RE_NON_EDITED_PAGE = re.compile("paper.([0-9]+).(png|jpg)")

    def _prefer_edited(self, file_names):
        for file_name in list(file_names):
            match = self.RE_NON_EDITED_PAGE.match(file_name)
            if match is None:
                continue
            (page_idx, file_ext) = match.groups()
            edited = f"paper.{page_idx}.edited.{file_ext}"
            if edited in file_names:
                file_names.remove(file_name)
        return file_names

    RE_ALL_PAGE = re.compile("paper.([0-9]+).(edited.|)(png|jpg)")

    def _sort_pages(self, file_names):
        file_names = [
            (
                (
                    int(self.RE_ALL_PAGE.match(file_name).group(1))
                    if self.RE_ALL_PAGE.match(file_name) is not None
                    else -1
                ),
                file_name
            )
            for file_name in file_names
        ]
        file_names.sort()

        file_names = [file_name for (page_idx, file_name) in file_names]
        return file_names

    def insert(self, core, db_cursor, doc_id, doc_url):
        if self.db_table_doc.doc_db_id is None:
            return

        files = core.call_success("fs_listdir", doc_url)
        files = [core.call_success("fs_basename", file) for file in files]
        files = [f for f in files if self._is_whitelisted(f)]
        files = self._prefer_edited(files)
        files = self._sort_pages(files)
        for file_name in files:
            core.call_one(
                "sqlite_execute", db_cursor.execute,
                "INSERT INTO Part (documentId, name)"
                " VALUES (?, ?)",
                (
                    self.db_table_doc.doc_db_id,
                    file_name,
                )
            )


class DbTableLabel(AbstractDbTable):
    CREATE_TABLE_QUERIES = [
        (
            "CREATE TABLE IF NOT EXISTS Label ("
            " labelId INTEGER NOT NULL PRIMARY KEY,"
            " documentId INTEGER NOT NULL,"
            " name TEXT NOT NULL,"
            " color TEXT,"
            " CONSTRAINT fkDocument"
            "  FOREIGN KEY (documentId)"
            "  REFERENCES Document(documentId)"
            "  ON DELETE CASCADE"
            ");"
        ),
        "CREATE INDEX IF NOT EXISTS Label_documentId on Label(documentId);",
        "CREATE INDEX IF NOT EXISTS Label_name on Label(name);",
    ]

    def __init__(self, db_table_doc: DbTableDocument):
        self.db_table_doc = db_table_doc

    def delete(self, core, doc_db_cursor, doc_id, doc_url):
        # Handled by "ON DELETE CASCADE"
        pass

    def insert(self, core, db_cursor, doc_id, doc_url):
        if self.db_table_doc.doc_db_id is None:
            return
        labels = set()
        core.call_all("doc_get_labels_by_url", labels, doc_url)
        for (label, color) in labels:
            core.call_one(
                "sqlite_execute", db_cursor.execute,
                "INSERT INTO Label(documentId, name, color) VALUES (?, ?, ?)",
                (
                    self.db_table_doc.doc_db_id,
                    label,
                    color,
                )
            )


class DbTableDocumentText(AbstractDbTable):
    CREATE_TABLE_QUERIES = [
        (
            "CREATE TABLE IF NOT EXISTS DocumentText ("
            " documentId INTEGER NOT NULL PRIMARY KEY,"
            " main TEXT NOT NULL,"
            " additional TEXT NULL,"
            " CONSTRAINT fkDocument"
            "  FOREIGN KEY (documentId)"
            "  REFERENCES Document(documentId)"
            "  ON DELETE CASCADE"
            ");"
        ),
        (
            "CREATE VIRTUAL TABLE IF NOT EXISTS DocumentFts USING FTS4("
            " tokenize=unicode61,"
            " content=`DocumentText`,"
            " main,"
            " additional"
            ");"
        ),
        # used by Room (see OpenPaperView)
        "PRAGMA user_version = 1;",
    ]

    def __init__(self, db_table_doc: DbTableDocument):
        self.db_table_doc = db_table_doc

    def delete(self, core, db_cursor, doc_id, doc_url):
        # With androidx.room, we cannot use foreign key in FTS table
        # -> we can't use "ON CASCADE DELETE"
        core.call_one(
            "sqlite_execute", db_cursor.execute,
            "DELETE FROM DocumentFts where rowid = ?",
            (self.db_table_doc.doc_db_id,)
        )

    def insert(self, core, db_cursor, doc_id, doc_url):
        text = []
        core.call_all("doc_get_text_by_url", text, doc_url)
        text = "\n".join(text)

        core.call_one(
            "sqlite_execute", db_cursor.execute,
            "INSERT INTO DocumentFts(rowid, main, additional) VALUES (?, ?, ?)",
            (
                self.db_table_doc.doc_db_id,
                text,
                "",
            )
        )
        core.call_one(
            "sqlite_execute", db_cursor.execute,
            "INSERT INTO DocumentText(rowid, main, additional) VALUES (?, ?, ?)",
            (
                self.db_table_doc.doc_db_id,
                text,
                "",
            )
        )

    def commit(self, core, db_cursor):
        LOGGER.info("Optimizing OpenPaperView FTS table ...")

        core.call_one(
            "sqlite_execute", db_cursor.execute,
            "INSERT INTO DocumentFts(DocumentFts) VALUES('optimize')"
        )
        LOGGER.info("OpenPaperView FTS table optimized")


DB_TABLE_DOC = DbTableDocument()

DB_TABLES = [
    DB_TABLE_DOC,
    DbTablePart(DB_TABLE_DOC),
    DbTableLabel(DB_TABLE_DOC),
    DbTableDocumentText(DB_TABLE_DOC),
]


class OpenPaperviewIndexTransaction(paperwork_backend.sync.BaseTransaction):
    def __init__(self, plugin, total_expected=-1):
        super().__init__(plugin.core, total_expected)
        self.plugin = plugin
        self.db_path = plugin.db_path
        self.core = plugin.core

        DB_LOCK.acquire()

        self.plugin.last_query = None

        self.sql = self.core.call_success(
            "sqlite_execute",
            self.core.call_success, "sqlite_open", self.db_path
        )
        self.cursor = self.core.call_success(
            "sqlite_execute",
            self.sql.cursor
        )
        self.core.call_one(
            "sqlite_execute", self.cursor.execute, "BEGIN TRANSACTION"
        )

    def add_doc(self, doc_id):
        self.notify_progress(ID, _("Document %s added") % (doc_id))
        self._add_doc(doc_id)
        super().add_doc(doc_id)

    def _add_doc(self, doc_id):
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        for db_table in DB_TABLES:
            db_table.insert(self.core, self.cursor, doc_id, doc_url)

    def _del_doc(self, doc_id):
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        for db_table in DB_TABLES:
            db_table.delete(self.core, self.cursor, doc_id, doc_url)

    def upd_doc(self, doc_id):
        self.notify_progress(ID, _("Document %s updated") % (doc_id))
        self._del_doc(doc_id)
        self._add_doc(doc_id)
        super().upd_doc(doc_id)

    def del_doc(self, doc_id):
        self.notify_progress(ID, _("Document %s deleted") % (doc_id))
        self._del_doc(doc_id)
        super().del_doc(doc_id)

    def unchanged_doc(self, doc_id):
        self.notify_progress(
            ID, _("Examining document %s: unchanged") % (doc_id)
        )
        super().unchanged_doc(doc_id)

    def cancel(self):
        self.notify_progress(ID, _("Rolling back changes"))
        self.core.call_one("sqlite_execute", self.cursor.execute, "ROLLBACK")
        self.core.call_one("sqlite_execute", self.cursor.close)
        self.core.call_one("sqlite_execute", self.sql.close)
        DB_LOCK.release()
        self.notify_done(ID)
        super().cancel()

    def commit(self):
        self.notify_progress(ID, _("Committing changes"))
        for db_table in DB_TABLES:
            db_table.commit(self.core, self.cursor)
        self.core.call_one("sqlite_execute", self.cursor.execute, "COMMIT")
        self.core.call_one("sqlite_execute", self.cursor.execute, "VACUUM")
        self.core.call_one("sqlite_execute", self.cursor.execute, "PRAGMA optimize")
        self.core.call_one("sqlite_execute", self.cursor.execute, "ANALYZE")
        self.core.call_one("sqlite_execute", self.cursor.close)
        self.core.call_one("sqlite_execute", self.sql.commit)
        self.core.call_one("sqlite_execute", self.sql.close)
        DB_LOCK.release()
        self.notify_done(ID)
        super().commit()


class Plugin(
        openpaperwork_core.PluginBase,
        metaclass=openpaperwork_core.util.Singleton):

    PRIORITY = 100

    def get_interfaces(self):
        return [
            "http_backend_extension",
            "sync",
        ]

    def get_deps(self):
        return [
            {
                "interface": "extra_text",
                "defaults": ["paperwork_backend.model.extra_text"],
            },
            {
                "interface": "data_dir_handler",
                "defaults": ["paperwork_backend.datadirhandler"],
            },
            {
                "interface": "doc_labels",
                "defaults": [
                    "paperwork_backend.model.labels",
                ],
            },
            {
                "interface": "doc_text",
                "defaults": [
                    "paperwork_backend.model.extra_text",
                    "paperwork_backend.model.hocr",
                    "paperwork_backend.model.pdf",
                ],
            },
            {
                "interface": "fs",
                "defaults": ["openpaperwork_core.fs.python"],
            },
            {
                "interface": "https_backend",
                "defaults": ["paperwork_backend.http"],
            },
            {
                "interface": "nb_pages",
                "defaults": ["paperwork_backend.model"],
            },
            {
                "interface": "sqlite",
                "defaults": ["openpaperwork_core.sqlite"],
            },
            {
                "interface": "thread",
                "defaults": ["openpaperwork_core.thread.simple"],
            },
        ]

    def __init__(self):
        self.db_path = None
        self.last_query = False

    def init(self, core):
        super().init(core)
        self.on_data_dir_changed()
        self.core.call_all("config_add_observer", "https_server", self.on_data_dir_changed)

    def on_data_dir_changed(self):
        if not self.core.call_success("config_get", "https_server"):
            return
        self.db_path = self.core.call_success(
            "fs_join",
            self.core.call_success("data_dir_handler_get_individual_data_dir"),
            "openpaperview.sqlite"
        )
        sql = self.core.call_success("sqlite_open", self.db_path)
        for table in DB_TABLES:
            for query in table.CREATE_TABLE_QUERIES:
                sql.execute(query)

    def doc_transaction_start(self, out: list, total_expected=-1):
        if not self.core.call_success("config_get", "https_server"):
            return
        out.append(OpenPaperviewIndexTransaction(self, total_expected))

    def _prepare_sync(self, storage_docs):
        storage_docs.sort()
        sql = self.core.call_success(
            "sqlite_execute",
            self.core.call_success, "sqlite_open", self.db_path
        )
        comparable_docs = [
            paperwork_backend.sync.doctracker.ComparableDoc(self.core, doc_id, doc_url)
            for (doc_id, doc_url) in storage_docs
        ]

        db_docs = self.core.call_success(
            "sqlite_execute",
            sql.execute, "select name, mtime from Document",
        )
        db_docs = self.core.call_success(
            "sqlite_execute",
            list, db_docs,
        )
        self.core.call_success("sqlite_execute", sql.close)
        db_docs = [
            paperwork_backend.sync.doctracker.DbDoc(r)
            for r in db_docs
        ]

        total_expected = max(len(storage_docs), len(db_docs))
        doc_diff = paperwork_backend.sync.doctracker.DocDiff(
            self.core, ["openpaperview_index"],
            comparable_docs, db_docs,
            [OpenPaperviewIndexTransaction(self, total_expected)]
        )
        return doc_diff

    def sync(self, promises: list):
        if not self.core.call_success("config_get", "https_server"):
            return
        storage_all_docs = []
        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self.core.call_all,
            args=("storage_get_all_docs", storage_all_docs,)
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self._prepare_sync, storage_all_docs)
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, lambda sync: sync.run()
        ))
        promises.append(promise)

    def http_backend_head(self, path: str) -> Optional[paperwork_backend.http.BackendReply]:
        return self.http_backend_get(path)

    # WORKAROUND(Jflesch):
    # OpenPaperView expects us to tell it when it has already downloaded
    # the latest version of the DB. But it doesn't provide the header
    # If-Modified-Since. So we play a little guessing game here ...
    WORKAROUND_FORCE_CACHE_TIME = int(os.getenv("OPENPAPERVIEW_WORKAROUND_FORCE_CACHE_TIME", 3600))

    def http_backend_get(self, request) -> Optional[paperwork_backend.http.BackendReply]:
        if request.path != QUERY_PATH:
            return None
        with DB_LOCK:
            now = time.perf_counter()
            last = self.last_query
            if last is not None and last + self.WORKAROUND_FORCE_CACHE_TIME > now:
                return paperwork_backend.http.BackendReply(
                    http_code=304,
                    last_modified=self.core.call_success("fs_get_mtime", self.db_path),
                    content_length=self.core.call_success("fs_getsize", self.db_path),
                )
            self.last_query = now

            return paperwork_backend.http.BackendReply(
                http_code=200,
                last_modified=self.core.call_success("fs_get_mtime", self.db_path),
                content_length=self.core.call_success("fs_getsize", self.db_path),
                content_fd=self.core.call_success("fs_open", self.db_path, "rb"),
                etag=self.core.call_success("fs_hash", self.db_path),
            )
