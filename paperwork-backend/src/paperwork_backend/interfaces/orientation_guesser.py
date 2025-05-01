import abc


class OrientationGuesser(abc.ABC):
    @abc.abstractmethod
    def guess_page_orientation_by_url(self, doc_url, page_idx):
        ...
