import abc


class Ocr(abc.ABC):
    @abc.abstractmethod
    def ocr_page_by_url(self, doc_url, page_idx):
        ...


class OcrSettings(abc.ABC):
    @abc.abstractmethod
    def ocr_get_active_langs(self):
        ...

    @abc.abstractmethod
    def ocr_set_active_langs(self, langs):
        ...

    @abc.abstractmethod
    def ocr_is_enabled(self):
        ...

    @abc.abstractmethod
    def ocr_add_observer_on_enabled(self, callback):
        ...

    @abc.abstractmethod
    def ocr_get_available_langs(self):
        ...
