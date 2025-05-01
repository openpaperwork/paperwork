from typing import Set
from typing import Tuple
import abc


class Index(abc.ABC):
    @abc.abstractmethod
    def index_search(
        self,
        out: Set[Tuple[str, str]],
        query,
        limit=None,
        search_type='fuzzy'
    ):
        ...

    @abc.abstractmethod
    def index_get_doc_id_by_hash(self, doc_hash):
        ...


class IndexListener(abc.ABC):
    @abc.abstractmethod
    def on_index_cancel(self):
        ...

    @abc.abstractmethod
    def on_index_updated(self):
        ...

    @abc.abstractmethod
    def on_index_commit_start(self):
        ...

    @abc.abstractmethod
    def on_index_commit_end(self):
        ...
