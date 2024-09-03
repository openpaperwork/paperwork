"""
This plugin is an helper for other plugins. It provides an easy way
to track pages that have not yet being treated in each document.

For instance, when a document is notified as updated (see transactions), the
OCR plugin needs to know which pages of this document have already been
OCR-ed and which haven't.
"""
import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)

CREATE_TABLES = [
    (
        "CREATE TABLE IF NOT EXISTS pages ("
        " doc_id TEXT NOT NULL,"
        " page INTEGER NOT NULL,"
        " hash TEXT NOT NULL,"
        " PRIMARY KEY (doc_id, page)"
        ")"
    ),
]


class PageTracker(object):
    def __init__(self, core, sql_url):
        self.core = core
        self.sql = self.core.call_one(
            "sqlite_execute",
            self.core.call_success,
            "sqlite_open", sql_url
        )
        for query in CREATE_TABLES:
            self.core.call_one("sqlite_execute", self.sql.execute, query)

        self.core.call_one(
            "sqlite_execute", self.sql.execute, "BEGIN TRANSACTION"
        )

    def _close(self):
        LOGGER.info("Closing page tracker db ...")
        self.core.call_one(
            "sqlite_execute",
            self.core.call_success,
            "sqlite_close", self.sql
        )
        self.sql = None

    def cancel(self):
        if self.sql is None:
            return
        self.core.call_one(
            "sqlite_execute", self.sql.execute, "ROLLBACK"
        )
        self._close()

    def commit(self):
        if self.sql is None:
            return
        self.core.call_one("sqlite_execute", self.sql.execute, "COMMIT")
        self._close()

    def find_changes(self, doc_id, doc_url):
        """
        Examine a document. Return page that haven't been handled yet
        or that have been modified since.
        Don't forget to call ack_page() once you've handled each page.
        """

        out = []

        db_pages = self.core.call_one(
            "sqlite_execute", self.sql.execute,
            "SELECT page, hash FROM pages"
            " WHERE doc_id = ?",
            (doc_id,)
        )
        db_pages = self.core.call_one(
            "sqlite_execute",
            lambda pages: {r[0]: int(r[1], 16) for r in pages}, db_pages
        )
        db_hashes = set(db_pages.values())

        fs_nb_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", doc_url
        ) or 0
        fs_pages = {}
        for page_idx in range(0, fs_nb_pages):
            fs_pages[page_idx] = self.core.call_success(
                "page_get_hash_by_url", doc_url, page_idx
            )

        for (page_idx, fs_page_hash) in fs_pages.items():
            if page_idx not in db_pages:
                out.append(('new', page_idx))
            else:
                db_page_hash = db_pages.pop(page_idx)
                if db_page_hash != fs_page_hash:
                    if fs_page_hash in db_hashes:
                        # this page existed before
                        out.append(('moved', page_idx))
                    else:
                        out.append(('upd', page_idx))

        for (db_page_idx, h) in db_pages.items():
            self.core.call_one(
                "sqlite_execute", self.sql.execute,
                "DELETE FROM pages"
                " WHERE doc_id = ? AND page = ?",
                (doc_id, db_page_idx)
            )

        return out

    def ack_page(self, doc_id, doc_url, page_idx):
        """
        Mark the page update has handled.
        """
        page_hash = self.core.call_success(
            "page_get_hash_by_url", doc_url, page_idx
        )
        self.core.call_one(
            "sqlite_execute", self.sql.execute,
            "INSERT OR REPLACE"
            " INTO pages (doc_id, page, hash)"
            " VALUES (?, ?, ?)",
            (doc_id, page_idx, format(page_hash, 'x'))
        )

    def delete_doc(self, doc_id):
        self.core.call_one(
            "sqlite_execute", self.sql.execute,
            "DELETE FROM pages WHERE doc_id = ?",
            (doc_id,)
        )


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        pass

    def get_interfaces(self):
        return ['page_tracking']

    def get_deps(self):
        return [
            {
                'interface': 'data_dir_handler',
                'defaults': ['paperwork_backend.datadirhandler'],
            },
            {
                'interface': 'data_versioning',
                'defaults': ['openpaperwork_core.data_versioning'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio']
            },
            {
                'interface': 'page_boxes',
                'defaults': ['paperwork_backend.model.hocr'],
            },
            {
                'interface': 'page_img',
                'defaults': [
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.pdf',
                ],
            },
            {
                'interface': 'sqlite',
                'defaults': ['openpaperwork_core.sqlite'],
            },
        ]

    def page_tracker_get(self, tracking_id):
        paperwork_dir = self.core.call_success(
            "data_dir_handler_get_individual_data_dir"
        )
        sql_file = self.core.call_success(
            "fs_join", paperwork_dir,
            'page_tracking_{}.db'.format(tracking_id)
        )
        return PageTracker(self.core, sql_file)
