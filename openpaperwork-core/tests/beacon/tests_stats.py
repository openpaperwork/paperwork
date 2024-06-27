import datetime
import http
import http.server
import json
import unittest
import threading
import time
import urllib

import openpaperwork_core


class TestStats(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)

        class FakeAppModule(object):
            class Plugin(openpaperwork_core.PluginBase):
                def get_interfaces(self):
                    return ['app']

                def app_get_name(self):
                    return "Paperwork"

                def app_get_fs_name(self):
                    return "paperwork2"

                def app_get_version(self):
                    return "2.1"

        self.core._load_module("fake_app", FakeAppModule())
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("openpaperwork_core.beacon.stats")

        self.config = self.core.get_by_name("openpaperwork_core.config.fake")
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

        with http.server.HTTPServer(('', 0), TestRequestHandler) as h:
            self.config.settings = {
                "send_statistics": True,
                "uuid": 1245,
                "statistics_last_run": datetime.date(1995, 1, 1),
                "statistics_protocol": "http",
                "statistics_server": "127.0.0.1:{}".format(h.server_port),
            }

            threading.Thread(target=h.handle_request).start()
            time.sleep(0.1)

            class FakeModule(object):
                class Plugin(openpaperwork_core.PluginBase):
                    def stats_get(self, stats):
                        stats['nb_documents'] += 122
                        stats['truck'] = 42

                    def on_stats_sent(s):
                        self.stats_sent = True

            self.core._load_module(
                "fake_module", FakeModule()
            )

            self.core.init()
            self.core.call_all("mainloop_quit_graceful")

            self.core.call_one('mainloop')

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

        with http.server.HTTPServer(('', 0), TestRequestHandler) as h:
            self.config.settings = {
                "send_statistics": True,
                "uuid": 1245,
                "statistics_last_run": datetime.date(1995, 1, 1),
                "statistics_protocol": "http",
                "statistics_server": "127.0.0.1:{}".format(h.server_port),
            }

            threading.Thread(target=h.handle_request).start()
            time.sleep(0.1)

            class FakeModule(object):
                class Plugin(openpaperwork_core.PluginBase):
                    def stats_get(self, stats):
                        stats['nb_documents'] += 122
                        stats['truck'] = 42

                    def on_stats_sent(s):
                        self.stats_sent = True

            self.core._load_module(
                "fake_module", FakeModule()
            )

            self.core.init()
            self.core.call_all("mainloop_quit_graceful")

            self.core.call_one('mainloop')

            self.assertFalse(self.stats_sent)
