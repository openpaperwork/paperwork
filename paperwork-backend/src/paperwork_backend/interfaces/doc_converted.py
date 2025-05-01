import abc


class DocConverted(abc.ABC):
    @abc.abstractmethod
    def doc_is_converted(self, doc_url):
        ...

    @abc.abstractmethod
    def doc_converted_check(self, doc_url):
        ...

    @abc.abstractmethod
    def doc_convert_and_import(self, file_url):
        ...
