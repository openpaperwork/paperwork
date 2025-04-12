import abc


class Print(abc.ABC):
    @abc.abstractmethod
    def print(self, txt: str):
        ...

    @abc.abstractmethod
    def print_isatty(self):
        ...

    @abc.abstractmethod
    def print_flush(self):
        ...
