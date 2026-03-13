import logging
import os
import sqlite3

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.sqlite import Sqlite
import openpaperwork_core

LOGGER = logging.getLogger(__name__)

# Beware that we use Sqlite, but sqlite python module is not thread-safe
# --> all the calls to sqlite module functions must happen on the main loop,
# even those in the transactions (which are run in a thread)


class Plugin(
    openpaperwork_core.PluginBase,
    Sqlite,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=["openpaperwork_core.fs.python"],
            ),
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=['openpaperwork_core.mainloop.asyncio'],
            ),
        ]

    def sqlite_open(self, db_url, *args, **kwargs):
        LOGGER.info("Opening DB %s ...", db_url)
        db_path = self.core.call_success(Fs.fs_unsafe, db_url)
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
        return self.core.call_one(Mainloop.mainloop_execute, cb, *args, **kwargs)

    def sqlite_schedule(self, cb, *args, **kwargs):
        return self.core.call_one(Mainloop.mainloop_schedule, cb, *args, **kwargs)

    def sqlite_close(self, db, optimize=True):
        if optimize:
            LOGGER.info("Optimizing database ...")
            db.execute("pragma optimize;")
        db.close()
        return True
