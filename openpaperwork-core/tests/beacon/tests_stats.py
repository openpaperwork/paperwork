import datetime
import http
import http.server
import json
import unittest
import threading
import time
import urllib

import openpaperwork_core
from openpaperwork_core.interfaces.app import App
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.stats import Stats
from openpaperwork_core.interfaces.stats import StatsListener


SERVER_PORT = 18080


class TestStats(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)

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

        self.core.load("fake_app", FakeAppModule())  # type: ignore
        self.core.load(
            "openpaperwork_core.config.fake",
            settings={
                "send_statistics": True,
                "uuid": 1245,
                "statistics_last_run": datetime.date(1995, 1, 1),
                "statistics_protocol": "http",
                "statistics_server": f"127.0.0.1:{SERVER_PORT}",
            }
        )
        self.core.load("openpaperwork_core.beacon.stats")

        self.received = []
        self.stats_sent = False

    def test_send_stats(self):
        self.received = []

        class TestRequestHandler(http.server.BaseHTTPRequestHandler):
            def do_POST(s):
                ctype = s.headers.get_content_type()
                if ctype == 'application/x-www-form-urlencoded':
                    length = int(s.headers['Content-Length'])
                    data = urllib.parse.parse_qs(
                        s.rfile.read(length), keep_blank_values=1
                    )
                else:
                    data = {}

                self.received.append(
                    (s.path, json.loads(data[b'statistics'][0]))
                )

                s.send_response(200)
                s.send_header('Content-type', 'text/html')
                s.end_headers()
                s.wfile.write(b"<html><body><p>OK</p></body></html>")

        with http.server.HTTPServer(('', SERVER_PORT), TestRequestHandler) as h:
            threading.Thread(target=h.handle_request).start()
            time.sleep(0.1)

            class FakeModule:
                __name__ = "fake_module"

                class Plugin(
                    openpaperwork_core.PluginBase,
                    Stats,
                    StatsListener,
                ):
                    def stats_get(self, out):
                        out['nb_documents'] += 122
                        out['truck'] = 42

                    def on_stats_sent(s):
                        self.stats_sent = True

            self.core.load("fake_module", FakeModule())  # type: ignore

            self.core.init()
            self.core.call_all(Mainloop.mainloop_quit_graceful)
            self.core.call_one(Mainloop.mainloop)

            self.assertTrue(self.stats_sent)
            self.assertEqual(len(self.received), 1)
            self.assertEqual(self.received[0][0], "/beacon/post_statistics")
            self.assertEqual(self.received[0][1]['uuid'], 1245)
            self.assertEqual(self.received[0][1]['nb_documents'], 122)
            self.assertEqual(self.received[0][1]['truck'], 42)

    def test_server_down(self):
        self.received = []

        class TestRequestHandler(http.server.BaseHTTPRequestHandler):
            def do_POST(s):
                ctype = s.headers.get_content_type()
                if ctype == 'application/x-www-form-urlencoded':
                    length = int(s.headers['Content-Length'])
                    data = urllib.parse.parse_qs(
                        s.rfile.read(length), keep_blank_values=1
                    )
                else:
                    data = {}

                self.received.append(
                    (s.path, json.loads(data[b'statistics'][0]))
                )

                s.send_response(500)
                s.send_header('Content-type', 'text/html')
                s.end_headers()
                s.wfile.write(b"<html><body><p>KO</p></body></html>")

        with http.server.HTTPServer(('', SERVER_PORT), TestRequestHandler) as h:
            threading.Thread(target=h.handle_request).start()
            time.sleep(0.1)

            class FakeModule:
                __name__ = "fake_module"

                class Plugin(
                    openpaperwork_core.PluginBase,
                    Stats,
                    StatsListener,
                ):
                    def stats_get(s, out):
                        out['nb_documents'] += 122
                        out['truck'] = 42

                    def on_stats_sent(s):
                        self.stats_sent = True

            self.core.load("fake_module", FakeModule())  # type: ignore

            self.core.init()
            self.core.call_all(Mainloop.mainloop_quit_graceful)
            self.core.call_one(Mainloop.mainloop)

            self.assertFalse(self.stats_sent)
