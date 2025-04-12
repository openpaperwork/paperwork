import http.server
import unittest

import ssl
import http.client

from openpaperwork_core.interfaces.app import App
from openpaperwork_core.interfaces.certificate_store import CertificateStore
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.https_server import AbstractRequestHandler
from openpaperwork_core.interfaces.https_server import HttpsServer
import openpaperwork_core
import openpaperwork_core.http.server


class MockRequestHandler(AbstractRequestHandler):
    def __init__(self):
        self.nb_heads = 0
        self.nb_gets = 0
        self.nb_posts = 0

    def do_HEAD(self, request):
        if not request.check_client_cert():
            return
        self.nb_heads += 1
        request.send_response(200, 'OK')
        request.end_headers()

    def do_GET(self, request):
        if not request.check_client_cert():
            return
        self.nb_gets += 1
        request.send_response(200, 'OK')
        request.send_header('Content-type', 'html')
        request.end_headers()
        request.wfile.write(bytes("<html><head><title>Hello World</title></head><body>", "UTF-8"))

    def do_POST(self, request):
        if not request.check_client_cert():
            return
        self.nb_posts += 1
        request.send_response(200, 'OK')
        request.send_header('Content-type', 'html')
        request.end_headers()
        request.wfile.write(bytes("<html><head><title>Hello World</title></head><body>", "UTF-8"))


class FakeAppModule:
    __name__ = "fake_app"

    class Plugin(
            openpaperwork_core.PluginBase,
            App,
    ):
        def app_get_name(self):
            return "Paperwork"

        def app_get_fs_name(self):
            return "paperwork2"

        def app_get_version(self):
            return "2.1"


class TestHttpsServer(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("fake_app", FakeAppModule())  # type: ignore
        self.core.load("openpaperwork_core.http.server")
        self.core.init()

    def _make_https_query(self, server_cert_name, client_cert_name, verb, path, expected=200):
        if client_cert_name is not None:
            client_cert = self.core.call_success(
                CertificateStore.store_certificate_get, client_cert_name
            )
        server_cert = self.core.call_success(
            CertificateStore.store_certificate_get, server_cert_name
        )
        ssl_context = ssl._create_unverified_context()

        if client_cert_name is not None:
            ssl_context.load_cert_chain(
                self.core.call_success(Fs.fs_unsafe, client_cert[0]),
                keyfile=self.core.call_success(Fs.fs_unsafe, client_cert[1]),
            )
        ssl_context.load_verify_locations(
            cafile=self.core.call_success(Fs.fs_unsafe, server_cert[0])
        )
        h = http.client.HTTPSConnection(
            host="127.0.0.1",
            port=12346,
            context=ssl_context,
        )
        try:
            h.request(verb, url=path)
            r = h.getresponse()
            self.assertEqual(r.status, expected)
        finally:
            h.close()

    def test_https_server(self):
        server_cert = self.core.call_success(
            CertificateStore.store_certificate_generate, "test_server"
        )
        self.core.call_success(
            CertificateStore.store_certificate_generate, "test_valid_client", parent=server_cert
        )
        other_server_cert = self.core.call_success(
            CertificateStore.store_certificate_generate, "test_other_server"
        )
        self.core.call_success(
            CertificateStore.store_certificate_generate, "test_invalid_client", parent=other_server_cert
        )

        mock = MockRequestHandler()
        https_server = self.core.call_success(
            HttpsServer.https_server_start, 12346,
            mock,
            server_cert_name="test_server",
            openpaperview_compatible=True,
        )
        try:
            self.assertIsNotNone(https_server)
            self._make_https_query("test_server", "test_valid_client", "GET", "/toto")
            self._make_https_query("test_other_server", None, "GET", "/toto", 403)
            self.assertRaises(
                ssl.SSLError,
                self._make_https_query, "test_other_server", "test_invalid_client", "GET", "/toto"
            )
        finally:
            https_server.stop()
        self.assertEqual(mock.nb_heads, 0)
        self.assertEqual(mock.nb_gets, 1)
        self.assertEqual(mock.nb_posts, 0)
