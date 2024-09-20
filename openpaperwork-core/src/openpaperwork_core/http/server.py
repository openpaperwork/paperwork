import abc
import logging
import ssl
import threading

from typing import Tuple
from typing import Type

import http.client
import http.server

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class BaseRequestHandler(abc.ABC):
    @abc.abstractmethod
    def do_HEAD(self, request):
        ...

    @abc.abstractmethod
    def do_POST(self, request):
        ...

    @abc.abstractmethod
    def do_GET(self, request):
        ...


class RequestHandlerWrapper(http.server.BaseHTTPRequestHandler):
    def __init__(self, wrapped_requested_handler: BaseRequestHandler, socket_ssl, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.wrapped_requested_handler = wrapped_requested_handler
        super().__init__(*args, **kwargs)

    def _check_client_cert(self):
        client_cert = self.connection.getpeercert(True)
        if client_cert is None:
            LOGGER.error("Missing client certificate !")
            self.send_response(403, "Missing client certificate")
            self.end_headers()
            return False
        return True

    def do_POST(self):
        LOGGER.info("POST %s", self.path)
        try:
            if not self._check_client_cert():
                return
            self.wrapped_requested_handler.do_POST(self)
        except Exception as exc:
            LOGGER.error("do_POST() failed: %s", repr(exc), exc_info=exc)

    def do_HEAD(self):
        LOGGER.info("HEAD %s", self.path)
        try:
            if not self._check_client_cert():
                return
            self.wrapped_requested_handler.do_HEAD(self)
        except Exception as exc:
            LOGGER.error("do_HEAD() failed: %s", repr(exc), exc_info=exc)

    def do_GET(self):
        LOGGER.info("GET %s", self.path)
        try:
            if not self._check_client_cert():
                return
            self.wrapped_requested_handler.do_GET(self)
        except Exception as exc:
            LOGGER.error("do_GET() failed: %s", repr(exc), exc_info=exc)


class HTTPSServer:
    def __init__(
            self,
            core,
            port,
            request_handler: Type[http.server.BaseHTTPRequestHandler],
            server_cert: Tuple[str, str],
            openpaperview_compatible: bool):
        self.core = core
        self.port = port
        self.request_handler = request_handler
        self.openpaperview_compatible = openpaperview_compatible

        LOGGER.info("Starting HTTPS server on port %d", port)
        self.httpd = http.server.HTTPServer(
            ("", port), self._build_request_handler,
        )

        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        self.ssl_context.load_cert_chain(
            self.core.call_success("fs_unsafe", server_cert[0]),
            keyfile=self.core.call_success("fs_unsafe", server_cert[1]),
        )
        self.ssl_context.load_verify_locations(
            cafile=self.core.call_success("fs_unsafe", server_cert[0])
        )
        self.ssl_context.verify_mode = (
            ssl.CERT_OPTIONAL
            if openpaperview_compatible
            else ssl.CERT_REQUIRED
        )
        self.httpd.socket = self.ssl_context.wrap_socket(self.httpd.socket, server_side=True)

        self.thread = threading.Thread(target=self._run, name="HTTPS server")
        self.thread.start()

    def _build_request_handler(self, *args, **kwargs):
        return RequestHandlerWrapper(self.request_handler, self.httpd.socket, *args, **kwargs)

    def _run(self):
        LOGGER.info("HTTPS server running")
        self.httpd.serve_forever()
        self.httpd.socket.close()
        LOGGER.info("HTTPS server stopped")

    def stop(self):
        LOGGER.info("Stopping HTTPS server")
        assert self.thread is not None
        self.httpd.shutdown()
        self.thread.join()
        self.thread = None


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ["https_server"]

    def get_deps(self):
        return [
            {
                'interface': 'certificate_store',
                'defaults': ['openpaperwork_core.crypto.certificates.store'],
            },
        ]

    def https_server_start(
            self,
            port: int,
            request_handler: Type[http.server.BaseHTTPRequestHandler],
            server_cert_name,
            openpaperview_compatible=True):
        """
        Will return an HTTPSServer instance.
        Will start an HTTPS server.

        This HTTPS server will only accept connections from certificates
        signed by the server certificate.
        """
        server_cert = self.core.call_success("store_certificate_get", server_cert_name)
        if server_cert is None:
            LOGGER.warning("Couldn't find server certificate '%s' !", server_cert)
            return None
        return HTTPSServer(self.core, port, request_handler, server_cert, openpaperview_compatible)
