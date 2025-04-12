import abc


class Urls(abc.ABC):
    @abc.abstractmethod
    def url_args_join(self, *args, **kwargs):
        ...

    @abc.abstractmethod
    def url_args_split(self, url):
        ...
