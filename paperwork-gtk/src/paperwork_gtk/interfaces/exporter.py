import abc


class GtkExporter(abc.ABC):
    @abc.abstractmethod
    def gtk_open_exporter(self, doc_id, doc_url):
        ...

    @abc.abstractmethod
    def gtk_open_exporter_multiple_docs(self, docs, ref_doc_id, ref_doc_url, ref_page_idx):
        ...
