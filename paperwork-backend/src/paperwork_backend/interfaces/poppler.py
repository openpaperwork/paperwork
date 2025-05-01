import abc


class Poppler(abc.ABC):
    @abc.abstractmethod
    def poppler_open(self, url, password=None):
        ...
