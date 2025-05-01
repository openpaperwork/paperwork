import abc


class DocPrint(abc.ABC):
    @abc.abstractmethod
    def doc_print(self, doc_id, doc_url, page_indexes=None):
        ...
