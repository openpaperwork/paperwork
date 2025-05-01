import abc


class Authors(abc.ABC):
    @abc.abstractmethod
    def authors_get(self, out: dict):
        ...
