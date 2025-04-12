import abc


class Display(abc.ABC):
    @abc.abstractmethod
    def print(self, txt):
        ...

    @abc.abstractmethod
    def print_flush(self):
        ...
