import abc


class DocLayout(abc.ABC):
    @abc.abstractmethod
    def gtk_open_layout_settings(self, *args, **kwargs):
        ...

    @abc.abstractmethod
    def gtk_close_layout_settings(self, *args, **kwargs):
        ...
