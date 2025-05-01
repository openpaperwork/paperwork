import abc


class DocImport(abc.ABC):
    @abc.abstractmethod
    def gtk_doc_import(self, file_urls):
        ...
