import abc


class Paths(abc.ABC):
    @abc.abstractmethod
    def paths_get_config_dir(self):
        ...

    @abc.abstractmethod
    def paths_get_data_dir(self):
        ...
