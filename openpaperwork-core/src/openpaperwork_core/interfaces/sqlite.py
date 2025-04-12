import abc


class Sqlite(abc.ABC):
    @abc.abstractmethod
    def sqlite_open(self, db_url, *args, **kwargs):
        ...

    @abc.abstractmethod
    def sqlite_execute(self, cb, *args, **kwargs):
        ...

    @abc.abstractmethod
    def sqlite_schedule(self, cb, *args, **kwargs):
        ...

    @abc.abstractmethod
    def sqlite_close(self, db, optimize=True):
        ...
