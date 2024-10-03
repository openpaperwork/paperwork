"""
Run an HTTPS exposing the work directory and a document index (sqlite).
Designed to be used with OpenPaperview
"""
from typing import BinaryIO, Optional
import dataclasses
import logging
import ssl

import openpaperwork_core
import openpaperwork_core.http.server
import openpaperwork_core.util

from paperwork_backend import _


SERVER_CERT_NAME = "backend_https_server"
CLIENT_CERT_NAME = "backend_https_client"


LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class BackendReply:
    HTTP_TEXTS = {
        200: "OK",
        304: "Not Modified",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not found",
    }
    BUFSIZE = 64 * 1024

    http_code: int
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    last_modified: Optional[int] = None
    etag: Optional[str] = None

    content_fd: Optional[BinaryIO] = None
    content_raw: Optional[bytes] = None

    def send(self, core, request):
        try:
            LOGGER.info(
                "HTTP %d: %s: %s",
                self.http_code, self.HTTP_TEXTS[self.http_code], repr(self)
            )
            request.send_response(self.http_code, self.HTTP_TEXTS[self.http_code])
            if self.content_length is not None:
                request.send_header("Content-Length", self.content_length)
            elif self.content_raw is not None:
                request.send_header("Content-Length", len(self.content_raw))
            if self.content_type is not None:
                request.send_header("Content-Type", self.content_type)
            else:
                request.send_header("Content-Type", "application/octet-stream")
            if self.last_modified is not None:
                request.send_header(
                    "Last-Modified",
                    request.date_time_string(self.last_modified)
                )
            if self.etag is not None:
                request.send_header("ETag", f'"{self.etag}"')
            # TODO(Jflesch): Must figure out why we need Connection=Close
            request.send_header("Connection", "close")
            request.end_headers()

            assert self.content_fd is None or self.content_raw is None
            if self.content_fd is not None:
                self._send_fd(core, request, self.content_fd)
            elif self.content_raw is not None:
                self._send_raw(core, request, self.content_raw)
        except ssl.SSLEOFError:
            LOGGER.warning("SSL EOF Error")
        finally:
            if self.content_fd is not None:
                self.content_fd.close()

    def _send_fd(self, core, request, fd):
        try:
            sent = 0
            while buf := fd.read(self.BUFSIZE):
                core.call_all(
                    "on_progress", "http_upload",
                    0 if self.content_length is None else (sent / self.content_length),
                    _("HTTPS server: Uploading %s") % (request.path)
                )
                request.wfile.write(buf)
                sent += len(buf)
        finally:
            core.call_all("on_progress", "http_upload", 1.0)

    def _send_raw(self, core, request, raw):
        try:
            for chunk in range(0, len(raw), self.BUFSIZE):
                start = chunk
                end = chunk + self.BUFSIZE
                core.call_all(
                    "on_progress", "http_upload", chunk / len(raw),
                    _("HTTPS server: Uploading %s") % (request.path)
                )
                request.wfile.write(raw[start:end])
        finally:
            core.call_all("on_progress", "http_upload", 1.0)


class BackendRequestHandler(openpaperwork_core.http.server.BaseRequestHandler):
    def __init__(self, core):
        self.core = core

    def _do(self, request, verb):
        headers = ", ".join([f"{k}={v}" for (k, v) in request.headers.items()])
        LOGGER.info("%s %s (%s)", verb.upper(), request.path, headers)
        assert self.core is not None
        if not self.core.call_success("http_backend_ignore_ssl_client_cert", request):
            if not request.check_client_cert():
                return
        r = self.core.call_success(f"http_backend_{verb.lower()}", request)
        if r is None:
            LOGGER.error("%s %s: 404", verb.upper(), request.path)
            request.send_response(404, "Not found")
            request.end_headers()
        else:
            r.send(self.core, request)

    def do_POST(self, request):
        self._do(request, "post")

    def do_HEAD(self, request):
        self._do(request, "head")

    def do_GET(self, request):
        self._do(request, "get")


class BackendHttpsServer:
    def __init__(self, core):
        self.core = core
        self.port = self.core.call_success("config_get", "https_port")
        self.server = self.core.call_success(
            "https_server_start",
            self.port,
            BackendRequestHandler(core),
            SERVER_CERT_NAME,
            self.core.call_success("config_get", "https_openpaperview_compatible"),
        )
        self.core.call_all("networking_announce_service", "paperwork", "https", self.port)

    def stop(self):
        self.core.call_all("networking_unannounce_service", "paperwork", "https", self.port)
        self.server.stop()


class Plugin(
        openpaperwork_core.PluginBase,
        metaclass=openpaperwork_core.util.Singleton):

    def get_interfaces(self):
        return [
            "https_backend",
        ]

    def get_deps(self):
        return [
            {
                "interface": "certificate_store",
                "defaults": ["openpaperwork_core.crypto.certificates.store"],
            },
            {
                "interface": "config",
                "defaults": ["openpaperwork_core.config"],
            },
            {
                "interface": "https_server",
                "defaults": ["openpaperwork_core.http.server"],
            },
        ]

    def init(self, core):
        super().init(core)

        self.server: Optional[BackendHttpsServer] = None

        self.core.call_all(
            "config_register", "https_server",
            self.core.call_success(
                "config_build_simple", "local_server", "https_server",
                lambda: False
            )
        )
        self.core.call_all(
            "config_register", "https_port",
            self.core.call_success(
                "config_build_simple", "local_server", "https_port",
                lambda: 12346
            )
        )
        self.core.call_all(
            "config_register", "https_openpaperview_compatible",
            self.core.call_success(
                "config_build_simple", "local_server", "openpaperview_compatible",
                lambda: True
            )
        )
        # We do not always start the HTTPS server now -> we don't
        # want to start it in CLI tools.

    def gtk_init(self, *args, **kwargs):
        self.core.call_all("config_add_observer", "https_server", self.https_backend_reload)
        self.https_backend_reload()

    def on_quit(self, *args, **kwargs):
        if self.server is not None:
            self.server.stop()
            self.server = None

    def https_backend_reload(self):
        if self.server is not None:
            self.server.stop()
            self.server = None

        active = self.core.call_success("config_get", "https_server")
        LOGGER.info("HTTPS server enabled=%s", active)
        if active:
            server_cert = self.core.call_success("store_certificate_get", SERVER_CERT_NAME)
            client_cert = self.core.call_success("store_certificate_get", CLIENT_CERT_NAME)
            if server_cert is None or client_cert is None:
                self.https_backend_regenerate_certificates()
            self.server = BackendHttpsServer(self.core)

    def https_backend_regenerate_certificates(self):
        server_cert = self.core.call_success(
            "store_certificate_generate", SERVER_CERT_NAME
        )
        self.core.call_success(
            "store_certificate_generate", CLIENT_CERT_NAME,
            parent=server_cert, embed_key=True
        )

    def https_backend_get_server_certificate(self):
        return self.core.call_success("store_certificate_get", SERVER_CERT_NAME)

    def https_backend_get_server_certificate_fingerprint(self):
        return self.core.call_success("store_certificate_get_fingerprint", SERVER_CERT_NAME)

    def https_backend_get_client_certificate(self):
        return self.core.call_success("store_certificate_get", CLIENT_CERT_NAME)
