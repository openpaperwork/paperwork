import abc


class DocOpener(abc.ABC):
    @abc.abstractmethod
    def doc_open(self, doc_id, doc_url):
        ...

    @abc.abstractmethod
    def doc_close(self):
        ...

    @abc.abstractmethod
    def doc_reload(self):
        ...


class NewDocOpener(abc.ABC):
    @abc.abstractmethod
    def doc_open_new(self):
        ...


class DocType(abc.ABC):
    @abc.abstractmethod
    def is_doc(self, doc_url) -> bool | None:
        ...

    @abc.abstractmethod
    def doc_internal_get_mtime_by_url(self, out: list, doc_url):
        ...

    @abc.abstractmethod
    def doc_internal_get_nb_pages_by_url(self, out: list, doc_url):
        ...


class DocText(abc.ABC):
    @abc.abstractmethod
    def doc_get_text_by_url(self, out: list, doc_url):
        ...

    @abc.abstractmethod
    def doc_get_title_by_url(self, doc_url):
        ...


class DocExtraText(abc.ABC):
    @abc.abstractmethod
    def doc_get_extra_text_by_url(self, out: list, doc_url):
        ...

    @abc.abstractmethod
    def doc_set_extra_text_by_url(self, doc_url, text):
        ...


class DocHash(abc.ABC):
    @abc.abstractmethod
    def doc_get_hash_by_url(self, doc_url):
        ...


class Docs(abc.ABC):
    @abc.abstractmethod
    def doc_get_nb_pages_by_url(self, doc_url) -> int | None:
        ...

    @abc.abstractmethod
    def doc_get_mtime_by_url(self, doc_url):
        ...
