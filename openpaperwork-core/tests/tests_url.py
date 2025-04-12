import unittest

from openpaperwork_core.interfaces.urls import Urls
import openpaperwork_core


class TestUrl(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.urls")
        self.core.init()

    def test_url_join(self):
        self.assertEqual(
            self.core.call_success(Urls.url_args_join, "file://something.txt"),
            "file://something.txt"
        )
        self.assertEqual(
            self.core.call_success(
                Urls.url_args_join, "file://something.txt", page=1
            ),
            "file://something.txt#page=1"
        )
        self.assertEqual(
            self.core.call_success(
                Urls.url_args_join, "file://something.txt",
                page=1, password="test1234"
            ),
            "file://something.txt#page=1&password=test1234"
        )

    def test_url_split(self):
        self.assertEqual(
            self.core.call_success(Urls.url_args_split, "file://something.txt"),
            ("file://something.txt", {})
        )
        self.assertEqual(
            self.core.call_success(
                Urls.url_args_split, "file://something.txt#page=1"
            ),
            ("file://something.txt", {"page": "1"})
        )
        self.assertEqual(
            self.core.call_success(
                Urls.url_args_split,
                "file://something.txt#page=1&password=test1234"
            ),
            ("file://something.txt", {"page": "1", "password": "test1234"})
        )
