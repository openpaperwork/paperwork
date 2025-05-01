import abc


class Icon(abc.ABC):
    @abc.abstractmethod
    def icon_get_pixbuf(self, icon_name, size_px):
        ...
