import abc


class PageViewBoxes(abc.ABC):
    @abc.abstractmethod
    def pageview_get_boxes_by_id(self, doc_id, page_idx):
        ...

    @abc.abstractmethod
    def page_draw_box(self, *args, **kwargs):
        ...


class PageViewBoxesListener(abc.ABC):
    @abc.abstractmethod
    def on_page_boxes_loaded(self, page, boxes, spatial_index):
        ...


class PageViewBoxesAll(abc.ABC):
    @abc.abstractmethod
    def set_all_boxes_visible(self, visible):
        ...
