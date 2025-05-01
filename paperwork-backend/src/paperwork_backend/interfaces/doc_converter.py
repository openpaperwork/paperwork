import abc


class DocConverter(abc.ABC):
    @abc.abstractmethod
    def converter_get_file_types(self, out: list):
        ...

    @abc.abstractmethod
    def convert_file_to_pdf(self, doc_file_uri, mime_type, out_pdf_file_url):
        ...
