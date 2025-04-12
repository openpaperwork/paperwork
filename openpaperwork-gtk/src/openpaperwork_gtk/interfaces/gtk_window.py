import abc


class GtkWindowListener(abc.ABC):
    @abc.abstractmethod
    def on_gtk_window_opened(self, window):
        ...

    @abc.abstractmethod
    def on_gtk_window_closed(self, window):
        ...
