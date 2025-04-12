import abc


class Chkdeps(abc.ABC):
    @abc.abstractmethod
    def chkdeps(self, out: dict):
        ...
