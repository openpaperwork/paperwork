import abc


class BoxSelectionListener(abc.ABC):
    @abc.abstractmethod
    def on_page_boxes_selected(self, doc_id, doc_url, page_id, boxes):
        ...
