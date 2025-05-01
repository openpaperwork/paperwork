import abc


class Pdf2Cairo(abc.ABC):
    @abc.abstractmethod
    def pdf_page_to_cairo_surface(self, file_url, page_idx, password=None):
        ...


class Url2Cairo(abc.ABC):
    @abc.abstractmethod
    def url_to_cairo_surface(self, file_url):
        ...

    @abc.abstractmethod
    def url_to_cairo_surface_promise(self, file_url):
        ...


class AbstractCairoRenderer:
    @abc.abstractmethod
    def start(self):
        ...

    @abc.abstractmethod
    def render(self, force=False):
        ...

    @abc.abstractmethod
    def hide(self):
        ...

    @abc.abstractmethod
    def close(self):
        ...

    @abc.abstractmethod
    def draw(self, cairo_ctx):
        ...

    @abc.abstractmethod
    def blur(self):
        ...

    @abc.abstractmethod
    def unblur(self):
        ...


class CairoRendererFactory(abc.ABC):
    @abc.abstractmethod
    def cairo_renderer_by_url(self, work_queue_name, file_url, **kwargs):
        ...


class Cairo2Pillow(abc.ABC):
    @abc.abstractmethod
    def cairo_surface_to_pillow(self, surface):
        ...
