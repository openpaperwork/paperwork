import abc


class Pillow(abc.ABC):
    @abc.abstractmethod
    def url_to_img_size(self, file_url):
        ...

    @abc.abstractmethod
    def url_to_img_size_promise(self, file_url):
        ...

    @abc.abstractmethod
    def url_to_pillow(self, file_url):
        ...

    @abc.abstractmethod
    def url_to_pillow_promise(self, file_url):
        ...

    @abc.abstractmethod
    def pillow_to_url(self, img, file_url, format=None, quality=0.75):
        ...


class PillowUtil(abc.ABC):
    @abc.abstractmethod
    def pillow_get_error(self, error_id):
        ...

    @abc.abstractmethod
    def pillow_add_border(self, img, color="#a6a5a4", width=1):
        ...
