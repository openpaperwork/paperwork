import unittest

from openpaperwork_core.interfaces.config import Config
import openpaperwork_core

from paperwork_backend.interfaces.pages import PageImg
from paperwork_backend.interfaces.pages import PageManagement


class TestImg(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("openpaperwork_core.fs.fake")
        self.core.load("paperwork_backend.model.img")
        self.core.load("paperwork_backend.model.img_overlay")
        self.core.init()

        self.fs = self.core.get_by_name("openpaperwork_core.fs.fake")

    def test_get_png_img_urls(self):
        self.fs.fs = {
            "some_doc": {
                "paper.1.jpg": "put_an_image_here",
                "paper.2.png": "put_an_image_here",
                "paper.3.png": "put_an_image_here",
            },
        }

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 1, write=False
        )
        self.assertEqual(img_url, "file:///some_doc/paper.2.png")

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 1, write=True
        )
        self.assertEqual(img_url, "file:///some_doc/paper.2.edited.png")

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 3, write=False
        )
        self.assertEqual(img_url, None)

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 3, write=True
        )
        self.assertEqual(img_url, "file:///some_doc/paper.4.png")

    def test_get_png_edited_img_urls(self):
        self.fs.fs = {
            "some_doc": {
                "paper.1.jpg": "put_an_image_here",
                "paper.2.png": "put_an_image_here",
                "paper.2.edited.png": "put_an_image_here",
                "paper.3.png": "put_an_image_here",
            },
        }

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 1, write=False
        )
        self.assertEqual(img_url, "file:///some_doc/paper.2.edited.png")

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 1, write=True
        )
        self.assertEqual(img_url, "file:///some_doc/paper.2.edited.png")

    def test_png_reset_img(self):
        self.fs.fs = {
            "some_doc": {
                "paper.1.jpg": "put_an_image_here",
                "paper.2.png": "put_an_image_here",
                "paper.2.edited.png": "put_an_image_here",
                "paper.3.png": "put_an_image_here",
                "paper.3.edited.png": "put_an_image_here",
            },
        }

        self.core.call_all(
            PageManagement.page_reset_by_url, "file:///some_doc", 1
        )

        self.assertEqual(self.fs.fs, {
            "some_doc": {
                "paper.1.jpg": "put_an_image_here",
                "paper.2.png": "put_an_image_here",
                "paper.3.png": "put_an_image_here",
                "paper.3.edited.png": "put_an_image_here",
            },
        })

        self.core.call_all(
            PageManagement.page_reset_by_url, "file:///some_doc", 1
        )

        self.assertEqual(self.fs.fs, {
            "some_doc": {
                "paper.1.jpg": "put_an_image_here",
                "paper.2.png": "put_an_image_here",
                "paper.3.png": "put_an_image_here",
                "paper.3.edited.png": "put_an_image_here",
            },
        })

    def test_get_jpg_img_urls(self):
        self.core.call_all(Config.config_put, "model_img_overlay_format", "JPEG")

        self.fs.fs = {
            "some_doc": {
                "paper.1.png": "put_an_image_here",
                "paper.2.jpg": "put_an_image_here",
                "paper.3.jpg": "put_an_image_here",
            },
        }

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 1, write=False
        )
        self.assertEqual(img_url, "file:///some_doc/paper.2.jpg")

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 1, write=True
        )
        self.assertEqual(img_url, "file:///some_doc/paper.2.edited.jpg")

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 3, write=False
        )
        self.assertEqual(img_url, None)

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 3, write=True
        )
        # paperwork_backend.model.img remains configured to use PNG
        self.assertEqual(img_url, "file:///some_doc/paper.4.png")

    def test_get_jpg_edited_img_urls(self):
        self.core.call_all(Config.config_put, "model_img_overlay_format", "JPEG")

        self.fs.fs = {
            "some_doc": {
                "paper.1.png": "put_an_image_here",
                "paper.2.jpg": "put_an_image_here",
                "paper.2.edited.jpg": "put_an_image_here",
                "paper.3.jpg": "put_an_image_here",
            },
        }

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 1, write=False
        )
        self.assertEqual(img_url, "file:///some_doc/paper.2.edited.jpg")

        img_url = self.core.call_success(
            PageImg.page_get_img_url, "file:///some_doc", 1, write=True
        )
        self.assertEqual(img_url, "file:///some_doc/paper.2.edited.jpg")

    def test_jpg_reset_img(self):
        self.core.call_all(Config.config_put, "model_img_overlay_format", "JPEG")

        self.fs.fs = {
            "some_doc": {
                "paper.1.png": "put_an_image_here",
                "paper.2.jpg": "put_an_image_here",
                "paper.2.edited.jpg": "put_an_image_here",
                "paper.3.jpg": "put_an_image_here",
                "paper.3.edited.jpg": "put_an_image_here",
            },
        }

        self.core.call_all(
            PageManagement.page_reset_by_url, "file:///some_doc", 1
        )

        self.assertEqual(self.fs.fs, {
            "some_doc": {
                "paper.1.png": "put_an_image_here",
                "paper.2.jpg": "put_an_image_here",
                "paper.3.jpg": "put_an_image_here",
                "paper.3.edited.jpg": "put_an_image_here",
            },
        })

        self.core.call_all(
            PageManagement.page_reset_by_url, "file:///some_doc", 1
        )

        self.assertEqual(self.fs.fs, {
            "some_doc": {
                "paper.1.png": "put_an_image_here",
                "paper.2.jpg": "put_an_image_here",
                "paper.3.jpg": "put_an_image_here",
                "paper.3.edited.jpg": "put_an_image_here",
            },
        })
