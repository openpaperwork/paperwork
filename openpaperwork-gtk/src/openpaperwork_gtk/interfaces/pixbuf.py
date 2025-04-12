import abc


class PixbufPillow(abc.ABC):
    @abc.abstractmethod
    def pixbuf_to_pillow(self, pixbuf):
        ...

    @abc.abstractmethod
    def pillow_to_pixbuf(self, img):
        ...
