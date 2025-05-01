import abc


class Scan2DocListener(abc.ABC):
    @abc.abstractmethod
    def on_scan2doc_start(self, scan_id, doc_id, doc_url):
        ...

    @abc.abstractmethod
    def on_scan2doc_page_scanned(self, scan_id, doc_id, doc_url, nb_pages):
        ...

    @abc.abstractmethod
    def on_scan2doc_end(self, scan_id, doc_id, doc_url):
        ...


class Scan2Doc(abc.ABC):
    @abc.abstractmethod
    def scan2doc_scan_id_to_doc_id(self, scan_id):
        ...

    @abc.abstractmethod
    def scan2doc_doc_id_to_scan_id(self, doc_id):
        ...

    @abc.abstractmethod
    def scan2doc_promise(self, *args, doc_id=None, doc_url=None, **kwargs):
        ...
