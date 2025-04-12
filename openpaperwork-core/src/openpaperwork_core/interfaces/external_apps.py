import abc


class ExternalApps(abc.ABC):
    @abc.abstractmethod
    def external_app_open_file(self, file_url):
        ...

    @abc.abstractmethod
    def external_app_open_folder(self, folder_url):
        ...

    @abc.abstractmethod
    def external_app_can_send_as_attachment(self) -> None:
        ...

    @abc.abstractmethod
    def external_app_send_as_attachment(self, uri) -> None:
        ...
