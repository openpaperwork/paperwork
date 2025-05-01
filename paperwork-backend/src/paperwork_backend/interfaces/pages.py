import abc


class PageImg(abc.ABC):
    @abc.abstractmethod
    def page_get_img_url(self, doc_url, page_idx, write=False, **kwargs):
        ...

    @abc.abstractmethod
    def page_get_paper_size_by_url(self, doc_url, page_idx):
        ...


class PageType(abc.ABC):
    @abc.abstractmethod
    def page_internal_get_mtime_by_url(self, out: list, doc_url, page_idx):
        ...

    @abc.abstractmethod
    def page_internal_get_hash_by_url(self, out: list, doc_url, page_idx):
        ...


class PageManagement(abc.ABC):
    @abc.abstractmethod
    def page_delete_by_url(self, doc_url, page_idx):
        ...

    @abc.abstractmethod
    def page_move_by_url(
        self,
        source_doc_url, source_page_idx,
        dest_doc_url, dest_page_idx
    ):
        ...

    @abc.abstractmethod
    def page_reset_by_url(self, doc_url, page_idx):
        ...


class Pages(abc.ABC):
    @abc.abstractmethod
    def page_get_hash_by_url(self, doc_url, page_idx) -> int | None:
        ...

    @abc.abstractmethod
    def page_get_mtime_by_url(self, doc_url, page_idx):
        ...


class PageText(abc.ABC):
    @abc.abstractmethod
    def page_has_text_by_url(self, doc_url, page_idx):
        ...

    @abc.abstractmethod
    def page_get_text_by_url(self, doc_url, page_idx):
        ...

    @abc.abstractmethod
    def page_get_boxes_by_url(self, doc_url, page_idx):
        ...

    @abc.abstractmethod
    def page_set_boxes_by_url(self, doc_url, page_idx, boxes):
        ...
