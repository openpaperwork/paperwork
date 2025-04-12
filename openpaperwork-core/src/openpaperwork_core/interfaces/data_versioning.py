import abc


class DataVersioningListener(abc.ABC):
    @abc.abstractmethod
    def on_data_files_deleted(self):
        ...


class DataVersioning(abc.ABC):
    pass
