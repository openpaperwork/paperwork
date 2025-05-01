import abc


class Zoom(abc.ABC):
    @abc.abstractmethod
    def on_zoomable_widget_new(self, zoomable, adjustment):
        ...

    @abc.abstractmethod
    def on_zoomable_widget_destroy(self, zoomable, adjustment):
        ...
