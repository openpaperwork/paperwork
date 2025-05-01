from typing import List
import abc


class AbstractDocRenderer(abc.ABC):
    @abc.abstractmethod
    def get_preview_output(
        self, doc_id, doc_url, terminal_size=(80, 25),
        page_idx=0
    ):
        ...

    @abc.abstractmethod
    def get_doc_output(self, doc_id, doc_url, terminal_size=(80, 25)):
        ...

    @abc.abstractmethod
    def get_page_output(self, doc_id, doc_url, page_nb, terminal_size=(80, 25)):
        ...

    @abc.abstractmethod
    def get_doc_infos(self, doc_id, doc_url):
        ...

    @abc.abstractmethod
    def get_page_infos(self, doc_id, doc_url, page_nb):
        ...


class DocRendererFactory(abc.ABC):
    @abc.abstractmethod
    def doc_renderer_get(self, out: List[AbstractDocRenderer]):
        ...


class ImgRenderer(abc.ABC):
    @abc.abstractmethod
    def img_render(self, img, terminal_width=80):
        ...


class LabelRenderer(abc.ABC):
    @abc.abstractmethod
    def format_labels(self, labels, separator='\n'):
        ...
