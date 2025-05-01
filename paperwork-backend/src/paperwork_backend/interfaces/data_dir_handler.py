import abc


class DataDirListener(abc.ABC):
    @abc.abstractmethod
    def on_data_dir_changed(self):
        ...


class DataDirHandler(abc.ABC):
    @abc.abstractmethod
    def data_dir_handler_get_individual_data_dir(self):
        ...
