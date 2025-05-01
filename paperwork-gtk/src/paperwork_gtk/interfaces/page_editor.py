import abc


class PageEditor(abc.ABC):
    @abc.abstractmethod
    def gtk_open_page_editor(self, doc_id, doc_url, page_idx):
        ...
