import abc


class DocThumbnailer(abc.ABC):
    @abc.abstractmethod
    def thumbnail_from_img(self, img):
        ...


class DocThumbnail(abc.ABC):
    @abc.abstractmethod
    def thumbnail_get_doc(self, doc_url):
        ...

    @abc.abstractmethod
    def thumbnail_get_doc_promise(self, doc_url):
        ...

    @abc.abstractmethod
    def thumbnail_get_page(self, doc_url, page_idx):
        ...

    @abc.abstractmethod
    def thumbnail_get_page_promise(self, doc_url, page_idx):
        ...
