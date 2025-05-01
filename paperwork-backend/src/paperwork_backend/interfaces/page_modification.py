import abc


class PageModificationListener(abc.ABC):
    @abc.abstractmethod
    def on_page_modification_start(self, doc_id, page_idx):
        ...

    @abc.abstractmethod
    def on_page_modification_end(self, doc_id, page_idx):
        ...
