import abc


class Resources(abc.ABC):
    @abc.abstractmethod
    def resources_get_file(self, pkg, filename):
        ...

    @abc.abstractmethod
    def resources_get_dir(self, pkg, dirname):
        ...
