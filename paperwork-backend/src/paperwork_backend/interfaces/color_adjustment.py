import abc


class ColorAdjustment(abc.ABC):
    @abc.abstractmethod
    def adjust_page_colors_by_url(self, doc_url, page_idx):
        ...
