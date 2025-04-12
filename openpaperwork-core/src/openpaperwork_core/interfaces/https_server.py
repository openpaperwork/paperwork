import abc


class AbstractRequestHandler(abc.ABC):
    @abc.abstractmethod
    def do_HEAD(self, request):
        ...

    @abc.abstractmethod
    def do_POST(self, request):
        ...

    @abc.abstractmethod
    def do_GET(self, request):
        ...


class HttpsServer(abc.ABC):
    @abc.abstractmethod
    def https_server_start(
        self,
        port: int,
        request_handler: AbstractRequestHandler,
        server_cert_name,
        openpaperview_compatible=True
    ):
        ...
