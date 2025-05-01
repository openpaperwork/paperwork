import io
import os
import unittest

import PIL.Image

import openpaperwork_core

from paperwork_backend.interfaces.doc_thumbnail import DocThumbnail


class TestImg(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.fs.fake")
        self.core.load("paperwork_backend.model.img")
        self.core.load("paperwork_backend.model.thumbnail")
        self.core.init()

        with io.BytesIO() as fd:
            img = PIL.Image.open(
                os.path.dirname(os.path.abspath(__file__)) + "/test_img.png"
            )
            img = img.convert("RGB")
            img.save(fd, format="JPEG")
            fd.seek(0)
            self.raw_img = fd.read()

        self.fs = self.core.get_by_name("openpaperwork_core.fs.fake")

    def test_get_img_urls(self):
        self.fs.fs = {
            "some_doc": {
                "paper.1.jpg": self.raw_img,
            },
        }

        thumbnail = self.core.call_success(
            DocThumbnail.thumbnail_get_doc, "file:///some_doc"
        )
        self.assertEqual(thumbnail.size, (64, 32))
