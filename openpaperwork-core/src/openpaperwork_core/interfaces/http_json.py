import abc


class AbstractHttpJsonClient(abc.ABC):
    @abc.abstractmethod
    def get_request_promise(self, path):
        ...


class HttpJson(abc.ABC):
    @abc.abstractmethod
    def http_json_get_client(self, module_name: str) -> AbstractHttpJsonClient:
        ...
