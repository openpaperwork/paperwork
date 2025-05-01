"""
Run an HTTPS exposing the work directory and a document index (sqlite).
Designed to be used with OpenPaperview
"""
from typing import Optional
import email.utils
import logging
import ssl

from openpaperwork_core.interfaces.certificate_store import CertificateStore
from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.gui import GuiListener
from openpaperwork_core.interfaces.https_server import AbstractRequestHandler
from openpaperwork_core.interfaces.https_server import HttpsServer
from openpaperwork_core.interfaces.networking import NetworkingServiceAnnounce
from openpaperwork_core.interfaces.progress import ProgressListener
from openpaperwork_core.interfaces.quit import QuitListener
import openpaperwork_core
import openpaperwork_core.http.server
import openpaperwork_core.util

from paperwork_backend import _
from paperwork_backend.interfaces.http import AbstractBackendReply
from paperwork_backend.interfaces.http import HttpBackendExtension
from paperwork_backend.interfaces.http import HttpsBackend
from paperwork_backend.interfaces.http import HttpsBackendSsl


SERVER_CERT_NAME = "backend_https_server"
CLIENT_CERT_NAME = "backend_https_client"


LOGGER = logging.getLogger(__name__)


class BackendReply(AbstractBackendReply):
    HTTP_TEXTS = {
        200: "OK",
        304: "Not Modified",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not found",
    }
    BUFSIZE = 64 * 1024

    def send(self, core, request):
        self._check_cache_time(core, request)
        self._check_cache_etag(core, request)
        self._send(core, request)

    def _set_not_modified(self):
        self.http_code = 304
        if self.content_fd is not None:
            self.content_fd.close()
            self.content_fd = None
        if self.content_raw is not None:
            self.content_raw = None

    def _check_cache_time(self, core, request):
        if self.http_code != 200:
            return
        if self.last_modified is None:
            return
        if_modified_since = request.headers["If-Modified-Since"]
        if if_modified_since is None:
            return
        if_modified_since = email.utils.parsedate_to_datetime(if_modified_since)
        if if_modified_since < self.last_modified:
            return
        self._set_not_modified()

    def _check_cache_etag(self, core, request):
        if self.http_code != 200:
            return
        if self.etag is None:
            return
        etag = f'"{self.etag}"'
        if_none_match = request.headers["If-None-Match"]
        if if_none_match is None:
            return
        if_none_match = if_none_match.split(", ")
        if etag not in if_none_match:
            return

        self._set_not_modified()

    def _send(self, core, request):
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
                    ProgressListener.on_progress, "http_upload",
                    0 if self.content_length is None else (sent / self.content_length),
                    _("HTTPS server: Uploading %s") % (request.path)
                )
                request.wfile.write(buf)
                sent += len(buf)
        finally:
            core.call_all(ProgressListener.on_progress, "http_upload", 1.0)

    def _send_raw(self, core, request, raw):
        try:
            for chunk in range(0, len(raw), self.BUFSIZE):
                start = chunk
                end = chunk + self.BUFSIZE
                core.call_all(
                    ProgressListener.on_progress, "http_upload", chunk / len(raw),
                    _("HTTPS server: Uploading %s") % (request.path)
                )
                request.wfile.write(raw[start:end])
        finally:
            core.call_all(ProgressListener.on_progress, "http_upload", 1.0)


class BackendRequestHandler(AbstractRequestHandler):
    def __init__(self, core):
        self.core = core

    def _do(self, request, verb):
        headers = ", ".join([f"{k}={v}" for (k, v) in request.headers.items()])
        LOGGER.info("%s %s (%s)", verb.upper(), request.path, headers)
        assert self.core is not None
        if not self.core.call_success(HttpsBackendSsl.http_backend_ignore_ssl_client_cert, request):
            if not request.check_client_cert():
                return
        r = None
        if verb.lower() == "head":
            r = self.core.call_success(HttpBackendExtension.http_backend_head, request)
        elif verb.lower() == "get":
            r = self.core.call_success(HttpBackendExtension.http_backend_get, request)
        elif verb.lower() == "post":
            r = self.core.call_success(HttpBackendExtension.http_backend_post, request)
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
        self.port = self.core.call_success(Config.config_get, "https_port")
        self.server = self.core.call_success(
            HttpsServer.https_server_start,
            self.port,
            BackendRequestHandler(core),
            SERVER_CERT_NAME,
            self.core.call_success(Config.config_get, "https_openpaperview_compatible"),
        )
        self.core.call_all(
            NetworkingServiceAnnounce.networking_announce_service,
            "paperwork", "https", self.port
        )

    def stop(self):
        self.core.call_all(
            NetworkingServiceAnnounce.networking_unannounce_service,
            "paperwork", "https", self.port
        )
        self.server.stop()


class Plugin(
    openpaperwork_core.PluginBase,
    GuiListener,
    HttpsBackend,
    QuitListener,
    metaclass=openpaperwork_core.util.Singleton,
):

    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": CertificateStore,
                "defaults": ["openpaperwork_core.crypto.certificates.store"],
            },
            {
                "interface": Config,
                "defaults": ["openpaperwork_core.config"],
            },
            {
                "interface": HttpsServer,
                "defaults": ["openpaperwork_core.http.server"],
            },
            {
                "interface": HttpBackendExtension,
                "defaults": [],
                "optional": True,
            },
            {
                "interface": HttpsBackendSsl,
                "defaults": [],
                "optional": True,
            },
            {
                "interface": NetworkingServiceAnnounce,
                "defaults": [],
                "optional": True,
            },
            {
                "interface": ProgressListener,
                "defaults": [],
                "optional": True,
            },
        ]

    def __init__(self, core):
        super().__init__(core)

        self.server: Optional[BackendHttpsServer] = None

        self.core.call_all(
            Config.config_register, "https_server",
            self.core.call_success(
                Config.config_build_simple, "local_server", "https_server",
                lambda: False
            )
        )
        self.core.call_all(
            Config.config_register, "https_port",
            self.core.call_success(
                Config.config_build_simple, "local_server", "https_port",
                lambda: 12346
            )
        )
        self.core.call_all(
            Config.config_register, "https_openpaperview_compatible",
            self.core.call_success(
                Config.config_build_simple, "local_server", "openpaperview_compatible",
                lambda: True
            )
        )
        # We do not always start the HTTPS server now -> we don't
        # want to start it in CLI tools.

    def on_gui_initialized(self):
        self.core.call_all(Config.config_add_observer, "https_server", self.https_backend_reload)
        self.https_backend_reload()

    @openpaperwork_core.noop
    def new_mainwindow(self):
        pass

    def on_quit(self, *args, **kwargs):
        if self.server is not None:
            self.server.stop()
            self.server = None

    def https_backend_reload(self):
        if self.server is not None:
            self.server.stop()
            self.server = None

        active = self.core.call_success(Config.config_get, "https_server")
        LOGGER.info("HTTPS server enabled=%s", active)
        if active:
            server_cert = self.core.call_success(
                CertificateStore.store_certificate_get, SERVER_CERT_NAME
            )
            client_cert = self.core.call_success(
                CertificateStore.store_certificate_get, CLIENT_CERT_NAME
            )
            if server_cert is None or client_cert is None:
                self.https_backend_regenerate_certificates()
            self.server = BackendHttpsServer(self.core)

    def https_backend_regenerate_certificates(self):
        server_cert = self.core.call_success(
            CertificateStore.store_certificate_generate, SERVER_CERT_NAME
        )
        self.core.call_success(
            CertificateStore.store_certificate_generate, CLIENT_CERT_NAME,
            parent=server_cert, embed_key=True
        )

    def https_backend_get_server_certificate(self):
        return self.core.call_success(
            CertificateStore.store_certificate_get, SERVER_CERT_NAME
        )

    def https_backend_get_server_certificate_fingerprint(self):
        return self.core.call_success(
            CertificateStore.store_certificate_get_fingerprint, SERVER_CERT_NAME
        )

    def https_backend_get_client_certificate(self):
        return self.core.call_success(
            CertificateStore.store_certificate_get, CLIENT_CERT_NAME
        )
