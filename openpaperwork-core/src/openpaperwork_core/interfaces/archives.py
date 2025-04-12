import abc


class AbstractArchiveHandler(abc.ABC):
    @abc.abstractmethod
    def get_new(self, name=None):
        ...

    @abc.abstractmethod
    def get_archived(self):
        ...

    @abc.abstractmethod
    def delete_obsoletes(self):
        ...


class FileArchives(abc.ABC):
    @abc.abstractmethod
    def file_archive_get(self, storage_name, file_extension) -> AbstractArchiveHandler:
        ...
