import abc


class ExportPipes(abc.ABC):
    @abc.abstractmethod
    def export_get_pipe_by_name(self, name):
        ...

    @abc.abstractmethod
    def export_get_pipes_by_input(self, out: list, input_type):
        ...

    @abc.abstractmethod
    def export_get_pipes_by_doc_urls(self, out: list, doc_urls):
        ...

    @abc.abstractmethod
    def export_get_pipes_by_doc_url(self, out: list, doc_url):
        ...

    @abc.abstractmethod
    def export_get_pipes_by_page(self, out: list, doc_url, page_nb):
        ...
