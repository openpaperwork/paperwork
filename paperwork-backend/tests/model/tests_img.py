import unittest

from openpaperwork_core.interfaces.config import Config
import openpaperwork_core

from paperwork_backend.interfaces.docs import Docs
from paperwork_backend.interfaces.pages import PageImg


class TestImg(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("openpaperwork_core.fs.fake")
        self.core.load("paperwork_backend.model")
        self.core.load("paperwork_backend.model.img")
        self.core.init()

        self.fs = self.core.get_by_name("openpaperwork_core.fs.fake")

    def test_get_png_img_urls(self):
        self.fs.fs = {
            "some_doc": {
                "paper.1.png": "put_an_image_here",
                "paper.2.png": "put_an_image_here",
            },
        }

        nb_pages = self.core.call_success(
            Docs.doc_get_nb_pages_by_url, "file:///non_existing"
        )
        self.assertIsNone(nb_pages)
        nb_pages = self.core.call_success(
            Docs.doc_get_nb_pages_by_url, "file:///some_doc"
        )
        self.assertEqual(nb_pages, 2)

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 1
        )
        self.assertEqual(img_url, "file:///some_doc/paper.2.png")

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 2
        )
        self.assertIsNone(img_url)

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 2, write=True
        )
        self.assertEqual(img_url, "file:///some_doc/paper.3.png")

    def test_get_jpg_img_urls(self):
        self.core.call_all(Config.config_put, "model_img_format", "JPEG")

        self.fs.fs = {
            "some_doc": {
                "paper.1.jpg": "put_an_image_here",
                "paper.2.jpg": "put_an_image_here",
            },
        }

        nb_pages = self.core.call_success(
            Docs.doc_get_nb_pages_by_url, "file:///non_existing"
        )
        self.assertIsNone(nb_pages)
        nb_pages = self.core.call_success(
            Docs.doc_get_nb_pages_by_url, "file:///some_doc"
        )
        self.assertEqual(nb_pages, 2)

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 1
        )
        self.assertEqual(img_url, "file:///some_doc/paper.2.jpg")

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 2
        )
        self.assertIsNone(img_url)

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 2, write=True
        )
        self.assertEqual(img_url, "file:///some_doc/paper.3.jpg")
