import os
import platform
import unittest

import gi
gi.require_version('Libinsane', '1.0')
from gi.repository import Libinsane  # noqa: E402

import openpaperwork_core  # noqa: E402

import paperwork_backend.docscan.libinsane  # noqa: E402


class TestImageAssembler(unittest.TestCase):
    def test_assembler(self):
        assembler = paperwork_backend.docscan.libinsane.ImageAssembler(
            line_width=5
        )
        assembler.MIN_CHUNK_SIZE = 12
        self.assertIsNone(assembler.get_last_chunk())

        assembler.add_piece(b"abc")
        self.assertIsNone(assembler.get_last_chunk())

        assembler.add_piece(b"def")
        self.assertIsNone(assembler.get_last_chunk())

        assembler.add_piece(b"hij")
        self.assertIsNone(assembler.get_last_chunk())

        assembler.add_piece(b"klmn")
        self.assertEqual(assembler.get_last_chunk(), b"abcdefhijk")

        assembler.add_piece(b"abc")
        self.assertEqual(assembler.get_last_chunk(), b"abcdefhijk")

        assembler.add_piece(b"def")
        self.assertEqual(assembler.get_last_chunk(), b"abcdefhijk")

        assembler.add_piece(b"hij")
        self.assertEqual(assembler.get_last_chunk(), b"lmnabcdefh")

        self.assertEqual(
            assembler.get_image(),
            b"abcdefhijklmnabcdefhij"
        )


class TestLibinsane(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.init()
        self.config = self.core.get_by_name("openpaperwork_core.config.fake")

        self.core.load("openpaperwork_core.thread.simple")
        self.core.load("openpaperwork_core.work_queue.default")
        self.core.load("paperwork_backend.docscan.libinsane")

        self.called = False
        self.results = []

    def test_list_devs(self):
        self.core.init()

        # drop warnings logs from Libinsane because they pollute tests output
        plugin = self.core.get_by_name("paperwork_backend.docscan.libinsane")
        plugin.libinsane_logger.min_level = Libinsane.LogLevel.ERROR

        def get_devs(devs):
            # not much else we can test: depends on the system on which we are
            self.called = True

        promise = self.core.call_success("scan_list_scanners_promise")
        promise = promise.then(get_devs)
        promise.schedule()
        self.core.call_all("mainloop_quit_graceful")

        self.core.call_all("mainloop")

        self.assertTrue(self.called)

    # We need Sane test backend for this test
    @unittest.skipUnless(os.name == 'posix', reason="Linux only")
    # Test is broken on ARM 32bits for some reason
    @unittest.skipUnless(
        platform.machine() != "aarch64"
        and platform.architecture()[0] != "32bit",
        reason="not running on ARM64 or 32bits systems",
    )
    @unittest.skipUnless(
        platform.machine() != "armhf",
        reason="not running on ARM32",
    )
    def test_scan(self):
        TEST_DEV_ID = "libinsane:sane:test:0"

        class FakeModule(object):
            __name__ = "fake_module"

            class Plugin(openpaperwork_core.PluginBase):
                def on_scan_feed_start(s, scan_id):
                    self.results.append("on_scan_feed_start")

                def on_scan_page_start(s, *args, **kwargs):
                    self.results.append("on_scan_page_start")

                def on_scan_chunk(s, *args, **kwargs):
                    self.results.append("on_scan_chunk")

                def on_scan_page_end(s, *args, **kwargs):
                    self.results.append("on_scan_page_end")

                def on_scan_feed_end(s, scan_id):
                    self.results.append("on_scan_feed_end")

        self.core._load_module("fake_module", FakeModule())

        self.core.init()

        # drop warnings logs from Libinsane because they pollute tests output
        plugin = self.core.get_by_name("paperwork_backend.docscan.libinsane")
        plugin.libinsane_logger.min_level = Libinsane.LogLevel.ERROR

        def scan(sources):
            source = sources['flatbed']
            (scan_id, promise) = source.scan_promise(resolution=150)
            promise = promise.then(  # roll out the image generator
                lambda args: list(args[2])
            )
            promise = promise.then(source.close)
            self.core.call_success("scan_schedule", promise)
            self.called = True

        def get_sources_and_scan(scanner):
            promise = scanner.get_sources_promise()
            promise = promise.then(scan)
            self.core.call_success("scan_schedule", promise)

        promise = self.core.call_success(
            "scan_get_scanner_promise", TEST_DEV_ID
        )
        promise = promise.then(get_sources_and_scan)
        promise.schedule()
        self.core.call_all("mainloop_quit_graceful")

        self.core.call_all("mainloop")

        self.assertTrue(self.called)
        self.assertIn("on_scan_feed_start", self.results)
        self.assertIn("on_scan_page_start", self.results)
        self.assertIn("on_scan_chunk", self.results)
        self.assertIn("on_scan_page_end", self.results)
        self.assertIn("on_scan_feed_end", self.results)

    # We need Sane test backend for this test
    @unittest.skipUnless(os.name == 'posix', reason="Linux only")
    # Test is broken on ARM 32bits for some reason
    @unittest.skipUnless(
        platform.machine() != "aarch64"
        and platform.architecture()[0] != "32bit",
        reason="not running on ARM64 or 32bits systems",
    )
    @unittest.skipUnless(
        platform.machine() != "armhf",
        reason="not running on ARM32",
    )
    def test_scan_default(self):
        TEST_DEV_ID = "libinsane:sane:test:0"

        self.config.settings = {
            "scanner_dev_id": TEST_DEV_ID,
            "scanner_resolution": 150,
        }

        class FakeModule(object):
            __name__ = "fake_module"

            class Plugin(openpaperwork_core.PluginBase):
                def on_scan_feed_start(s, scan_id):
                    self.results.append("on_scan_feed_start")

                def on_scan_page_start(s, *args, **kwargs):
                    self.results.append("on_scan_page_start")

                def on_scan_chunk(s, *args, **kwargs):
                    self.results.append("on_scan_chunk")

                def on_scan_page_end(s, *args, **kwargs):
                    self.results.append("on_scan_page_end")

                def on_scan_feed_end(s, scan_id):
                    self.results.append("on_scan_feed_end")

        self.core._load_module("fake_module", FakeModule())

        self.core.init()

        # drop warnings logs from Libinsane because they pollute tests output
        plugin = self.core.get_by_name("paperwork_backend.docscan.libinsane")
        plugin.libinsane_logger.min_level = Libinsane.LogLevel.ERROR

        (scan_id, promise) = self.core.call_success(
            "scan_promise", source_id="flatbed"
        )
        promise = promise.then(  # roll out the image generator
            lambda args: list(args[2])
        )
        self.core.call_success("scan_schedule", promise)
        self.core.call_all("mainloop_quit_graceful")

        self.core.call_all("mainloop")

        self.assertIn("on_scan_feed_start", self.results)
        self.assertIn("on_scan_page_start", self.results)
        self.assertIn("on_scan_chunk", self.results)
        self.assertIn("on_scan_page_end", self.results)
        self.assertIn("on_scan_feed_end", self.results)
