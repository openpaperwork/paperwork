from typing import Set
from typing import Tuple
import abc


class DocSelecter(abc.ABC):
    @abc.abstractmethod
    def doc_selection_single(self):
        ...

    @abc.abstractmethod
    def doc_selection_multiple(self):
        ...


class DocSelection(abc.ABC):
    @abc.abstractmethod
    def doc_selection_reset(self):
        ...

    @abc.abstractmethod
    def doc_selection_add(self, doc_id, doc_url):
        ...

    @abc.abstractmethod
    def doc_selection_remove(self, doc_id, doc_url):
        ...

    @abc.abstractmethod
    def doc_selection_get(self, out: Set[Tuple[str, str]]):
        ...

    @abc.abstractmethod
    def doc_selection_len(self):
        ...

    @abc.abstractmethod
    def doc_selection_in(self, doc_id, doc_url):
        ...
