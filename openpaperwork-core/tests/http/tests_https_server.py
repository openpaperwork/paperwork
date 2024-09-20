import http.server
import unittest

import ssl
import http.client

import openpaperwork_core


class MockRequestHandler(http.server.BaseHTTPRequestHandler):
    nb_heads = 0
    nb_gets = 0
    nb_posts = 0

    def do_HEAD(self):
        MockRequestHandler.nb_heads += 1
        self.send_response(200, 'OK')
        self.end_headers()

    def do_GET(self):
        MockRequestHandler.nb_gets += 1
        self.send_response(200, 'OK')
        self.send_header('Content-type', 'html')
        self.end_headers()
        self.wfile.write(bytes("<html><head><title>Hello World</title></head><body>", "UTF-8"))

    def do_POST(self):
        MockRequestHandler.nb_posts += 1
        self.send_response(200, 'OK')
        self.send_header('Content-type', 'html')
        self.end_headers()
        self.wfile.write(bytes("<html><head><title>Hello World</title></head><body>", "UTF-8"))


class TestHttpsServer(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.http.server")
        self.core.init()

    def _make_https_query(self, server_cert_name, client_cert_name, verb, path, expected=200):
        if client_cert_name is not None:
            client_cert = self.core.call_success("store_certificate_get", client_cert_name)
        server_cert = self.core.call_success("store_certificate_get", server_cert_name)
        ssl_context = ssl._create_unverified_context()

        if client_cert_name is not None:
            ssl_context.load_cert_chain(
                self.core.call_success("fs_unsafe", client_cert[0]),
                keyfile=self.core.call_success("fs_unsafe", client_cert[1]),
            )
        ssl_context.load_verify_locations(
            cafile=self.core.call_success("fs_unsafe", server_cert[0])
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
            "store_certificate_generate", "test_server"
        )
        self.core.call_success(
            "store_certificate_generate", "test_valid_client", parent=server_cert
        )
        other_server_cert = self.core.call_success(
            "store_certificate_generate", "test_other_server"
        )
        self.core.call_success(
            "store_certificate_generate", "test_invalid_client", parent=other_server_cert
        )

        https_server = self.core.call_success(
            "https_server_start", 12346,
            MockRequestHandler,
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
        self.assertEqual(MockRequestHandler.nb_heads, 0)
        self.assertEqual(MockRequestHandler.nb_gets, 1)
        self.assertEqual(MockRequestHandler.nb_posts, 0)
