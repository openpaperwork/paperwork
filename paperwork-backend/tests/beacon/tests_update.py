import datetime
import http
import http.server
import json
import unittest
import threading
import time

from openpaperwork_core.interfaces.mainloop import Mainloop
from paperwork_backend.interfaces.update_detection import UpdateDetectionListener
import openpaperwork_core


SERVER_PORT = 18080


class TestUpdate(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(
            "openpaperwork_core.config.fake",
            settings = {
                "check_for_update": True,
                "last_update_found": "0.1.3",
                "update_last_run": datetime.date(1995, 1, 1),
                "update_protocol": "http",
                "update_server": f"127.0.0.1:{SERVER_PORT}",
            }
        )
        self.core.load("paperwork_backend.app")
        self.core.load("paperwork_backend.beacon.update")
        self.core.init()

        self.received = False

    def test_check_update(self):
        self.received = False

        class TestRequestHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(s):
                self.assertEqual(s.path, "/beacon/latest")
                s.send_response(200)
                s.send_header('Content-type', 'application/json')
                s.end_headers()
                s.wfile.write(json.dumps({
                    "paperwork": {
                        "posix": "999.1.2",
                        "nt": "999.1.2",
                    },
                }).encode("utf-8"))
                self.received = True

        with http.server.HTTPServer(('', SERVER_PORT), TestRequestHandler) as h:
            threading.Thread(target=h.handle_request).start()
            time.sleep(0.1)

            class FakeModule:
                __name__ = "fake_module"

                class Plugin(
                    openpaperwork_core.PluginBase,
                    UpdateDetectionListener,
                ):
                    def on_update_detected(s, current, new):
                        self.assertEqual(new, (999, 1, 2))
                        self.core.call_all(Mainloop.mainloop_quit_graceful)

            self.core.load("fake_module", FakeModule())  # type: ignore

            self.core.init()

            self.core.call_one(Mainloop.mainloop)

        self.assertTrue(self.received)

    def test_server_down(self):
        self.received = False
        self.update_notified = False

        class TestRequestHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(s):
                self.assertEqual(s.path, "/beacon/latest")
                s.send_response(500)
                s.send_header('Content-type', 'text/html')
                s.end_headers()
                s.wfile.write(b"<html><body><p>KO</p></body></html>")
                self.received = True

        with http.server.HTTPServer(('', SERVER_PORT), TestRequestHandler) as h:
            threading.Thread(target=h.handle_request).start()
            time.sleep(0.1)

            class FakeModule:
                __name__ = "fake_module"

                class Plugin(
                    openpaperwork_core.PluginBase,
                    UpdateDetectionListener,
                ):
                    def on_update_detected(s, current, new):
                        self.update_notified = True

            self.core.load("fake_module", FakeModule())  # type: ignore

            self.core.init()

            self.core.call_all(Mainloop.mainloop_quit_graceful)
            self.core.call_one(Mainloop.mainloop)

        self.assertTrue(self.received)
        self.assertFalse(self.update_notified)
