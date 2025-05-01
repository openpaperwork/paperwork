from typing import Tuple
import abc


class Cropping(abc.ABC):
    @abc.abstractmethod
    def crop_page_borders_by_url(self, doc_url, page_idx) -> Tuple[int, int, int, int]:
        ...


class PredefinedCropping(abc.ABC):
    pass
