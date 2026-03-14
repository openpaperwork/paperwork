import abc
import datetime


class DocStorageCache(abc.ABC):
    @abc.abstractmethod
    def flush_doc_cache(self, doc_url):
        ...


class DocStorageListener(abc.ABC):
    @abc.abstractmethod
    def on_storage_changed(self):
        ...


class DocStorage(abc.ABC):
    @abc.abstractmethod
    def doc_storage_get_name(self):
        ...

    @abc.abstractmethod
    def doc_id_to_url(self, doc_id, existing=True):
        ...

    @abc.abstractmethod
    def doc_url_to_id(self, doc_url):
        ...

    @abc.abstractmethod
    def doc_get_date_by_id(self, doc_id):
        ...

    @abc.abstractmethod
    def doc_get_id_by_date(self, date):
        ...

    @abc.abstractmethod
    def storage_get_id(self) -> str:
        ...

    @abc.abstractmethod
    def storage_get_all_docs(self, out: list, only_valid=True):
        ...

    @abc.abstractmethod
    def storage_get_new_doc(self, now_func=datetime.datetime.now):
        ...

    @abc.abstractmethod
    def storage_delete_doc_id(self, doc_id, trash=True):
        ...

    @abc.abstractmethod
    def doc_rename_by_url(self, src_doc_url, dst_doc_url):
        ...

    @abc.abstractmethod
    def doc_copy_by_url(self, src_doc_url):
        ...

    @abc.abstractmethod
    def doc_get_size_by_url(self, doc_url):
        ...
