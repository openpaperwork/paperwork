import abc


class App(abc.ABC):
    @abc.abstractmethod
    def app_get_name(self) -> str:
        ...

    @abc.abstractmethod
    def app_get_fs_name(self) -> str:
        ...

    @abc.abstractmethod
    def app_get_version(self) -> str:
        ...
