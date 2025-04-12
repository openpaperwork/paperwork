import os
import unittest

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.pillow import Pillow
import openpaperwork_core


class TestPillowImg(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.fs.python")
        self.core.load("openpaperwork_core.fs.memory")
        self.core.load("openpaperwork_core.pillow.img")
        self.core.init()

        self.img_path = self.core.call_success(
            Fs.fs_safe,
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "test_doc.png"
            )
        )

    def test_img_url_to_pillow(self):
        img = self.core.call_success(Pillow.url_to_pillow, self.img_path)
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (2380, 3364))

    def test_pillow_to_url(self):
        img = self.core.call_success(Pillow.url_to_pillow, self.img_path)

        (img_url, fd) = self.core.call_success(
            Fs.fs_mktemp, prefix="paperwork-test", suffix=".png"
        )
        fd.close()
        self.core.call_success(Pillow.pillow_to_url, img, img_url, format="PNG")

        # no real way to make sure the image was correctly written I guess

        self.core.call_success(Fs.fs_unlink, img_url, trash=False)
