"""
Run an HTTPS exposing the work directory and a document index (sqlite).
Designed to be used with OpenPaperview
"""
from typing import Optional
import logging
import ssl

import openpaperwork_core
import openpaperwork_core.http.server
import openpaperwork_core.util

from paperwork_backend import _


SERVER_CERT_NAME = "backend_https_server"
CLIENT_CERT_NAME = "backend_https_client"


LOGGER = logging.getLogger(__name__)


class BackendRequestHandler(openpaperwork_core.http.server.BaseRequestHandler):
    def __init__(self, core):
        self.core = core

    def do_POST(self, request):
        LOGGER.error("POST %s: 405", request.path)
        request.send_response(405, "Method not allowed")
        request.end_headers()

    def do_HEAD(self, request):
        assert self.core is not None
        r = self.core.call_success("http_backend_head", request.path)
        if r is None:
            LOGGER.error("HEAD %s: 404", request.path)
            request.send_response(404, "Not found")
            request.end_headers()
        else:
            (mtime, size) = r
            LOGGER.info("HEAD %s: OK (%dB)", request.path, size)
            request.send_response(200, "OK")
            request.send_header("Content-Length", size)
            request.send_header("Content-Type", "application/octet-stream")
            request.send_header("Last-Modified", request.date_time_string(mtime))
            request.end_headers()

    def _return_not_found(self, request):
        LOGGER.error("GET %s: 404", request.path)
        request.send_response(404, "Not found")
        request.end_headers()

    def _return_simple_code(self, request, http_code, mtime=None):
        LOGGER.info(
            "GET %s: %d",
            request.path, http_code,
        )
        request.send_response(http_code, str(http_code))
        if mtime is not None:
            request.send_header("Last-Modified", request.date_time_string(mtime))
        request.end_headers()

    def _return_bytes(self, request, mtime, content):
        LOGGER.info(
            "GET %s: OK (total=%dKB)",
            request.path, len(content) / 1024,
        )
        request.send_response(200, "OK")
        request.send_header("Content-Length", len(content))
        request.send_header("Content-Type", "application/octet-stream")
        request.send_header("Last-Modified", request.date_time_string(mtime))
        request.send_header("Cache-Control", "must-revalidate")
        request.end_headers()
        try:
            bufsize = 64 * 1024
            for chunk in range(0, len(content), bufsize):
                start = chunk
                end = chunk + bufsize
                LOGGER.debug(
                    "GET %s: OK (chunk=%d-%d)",
                    request.path, start, max(len(content), end)
                )
                self.core.call_all(
                    "on_progress", "http_upload", chunk / len(content),
                    _("HTTPS server: Uploading %s") % (request.path)
                )
                request.wfile.write(content[start:end])
        except ssl.SSLEOFError:
            LOGGER.warning("SSL EOF Error")
        finally:
            self.core.call_all("on_progress", "http_upload", 1.0)
        LOGGER.info("GET %s: OK (total=%d KB) sent", request.path, len(content) / 1024)

    def do_GET(self, request):
        assert self.core is not None
        r = self.core.call_success("http_backend_get", request.path)
        if r is None:
            self._return_not_found(request)
        else:
            (mtime, content) = r
            if isinstance(content, int):
                self._return_simple_code(request, content, mtime)
            else:  # content == bytes
                self._return_bytes(request, mtime, content)


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

    def https_backend_get_client_certificate(self):
        return self.core.call_success("store_certificate_get", CLIENT_CERT_NAME)
