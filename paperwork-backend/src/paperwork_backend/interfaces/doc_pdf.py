import abc


class DocPdf(abc.ABC):
    @abc.abstractmethod
    def doc_pdf_import(self, pdf_url):
        ...

    @abc.abstractmethod
    def doc_get_pdf_url_by_url(self, doc_url, write=False, allow_mapped=False):
        ...

    @abc.abstractmethod
    def doc_pdf_get_real_nb_pages_by_url(self, doc_url):
        ...
