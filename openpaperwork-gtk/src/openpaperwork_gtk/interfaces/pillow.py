import abc


class PillowDrawer(abc.ABC):
    @abc.abstractmethod
    def draw_pillow_start(self, drawing_area, pil_img):
        ...

    @abc.abstractmethod
    def draw_pillow_stop(self, drawing_area):
        ...


class Pillow2Cairo(abc.ABC):
    @abc.abstractmethod
    def pillow_to_surface(self, pillow, intermediate="pixbuf", quality=90):
        ...
