import abc


class PageDrawer(abc.ABC):
    @abc.abstractmethod
    def pageview_refresh_all(self):
        ...

    @abc.abstractmethod
    def on_page_draw(self, cairo_ctx, page):
        ...

    @abc.abstractmethod
    def on_page_visibility_changed(self, page, visible):
        ...
