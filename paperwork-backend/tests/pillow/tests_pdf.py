import os
import unittest

import PIL.Image

from openpaperwork_core.interfaces.pillow import Pillow
import openpaperwork_core
import openpaperwork_core.fs


class TestPillowPdf(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("paperwork_backend.pillow.pdf")
        self.core.init()

        self.pdf_url = openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "test_doc.pdf"
            )
        ) + "#page=1"
        self.img_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "test_doc.png"
        )

    def test_pdf_url_to_pillow(self):
        pdf_as_img = self.core.call_success(Pillow.url_to_pillow, self.pdf_url)
        ref_img = PIL.Image.open(self.img_path)
        self.assertEqual(ref_img.size, pdf_as_img.size)
