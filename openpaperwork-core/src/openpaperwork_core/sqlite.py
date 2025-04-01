import logging
import os
import sqlite3

from . import PluginBase

LOGGER = logging.getLogger(__name__)

# Beware that we use Sqlite, but sqlite python module is not thread-safe
# --> all the calls to sqlite module functions must happen on the main loop,
# even those in the transactions (which are run in a thread)


class Plugin(PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['sqlite']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
        ]

    def sqlite_open(self, db_url, *args, **kwargs):
        LOGGER.info("Opening DB %s ...", db_url)
        db_path = self.core.call_success("fs_unsafe", db_url)
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 60
        sql = sqlite3.connect(db_path, *args, **kwargs)
        sql.execute("pragma journal_mode = wal;")
        sql.execute("pragma synchronous = normal;")
        sql.execute("pragma temp_store = memory;")
        if os.name == "posix":
            sql.execute("pragma mmap_size = 30000000000;")
        return sql

    def sqlite_execute(self, cb, *args, **kwargs):
        return self.core.call_one("mainloop_execute", cb, *args, **kwargs)

    def sqlite_schedule(self, cb, *args, **kwargs):
        return self.core.call_one("mainloop_schedule", cb, *args, **kwargs)

    def sqlite_close(self, db, optimize=True):
        if optimize:
            LOGGER.info("Optimizing database ...")
            db.execute("pragma optimize;")
        db.close()
        return True
