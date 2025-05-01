import os
import shutil
import tempfile
import unittest

import PIL
import PIL.Image

from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.pillow import Pillow
import openpaperwork_core
import openpaperwork_core.fs

from paperwork_backend.interfaces.orientation_guesser import OrientationGuesser


class TestPyocr(unittest.TestCase):
    def setUp(self):
        self.tmp_paperwork_dir = tempfile.mkdtemp(
            prefix="paperwork_backend_tests"
        )

        self.test_img = PIL.Image.open(
            "{}/test_img.png".format(
                os.path.dirname(os.path.abspath(__file__))
            )
        )
        self.test_empty_img = PIL.Image.open(
            "{}/test_img2.png".format(
                os.path.dirname(os.path.abspath(__file__))
            )
        )

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.sync.doctracker")
        self.core.load("paperwork_backend.sync.pagetracker")
        self.core.load("paperwork_backend.guesswork.orientation.pyocr")

        class FakeModule:
            __name__ = "fake_module"

            class Plugin(
                openpaperwork_core.PluginBase,
                Pillow,
            ):
                PRIORITY = 10000000000

                def pillow_to_url(s, img, url):
                    self.pillowed.append(url)
                    return url

                def url_to_img_size(self, file_url):
                    pass

                def url_to_img_size_promise(self, file_url):
                    pass

                def url_to_pillow(self, file_url):
                    pass

                def url_to_pillow_promise(self, file_url):
                    pass

        self.core.load("fake_module", FakeModule())

        self.core.init()

        self.core.get_by_name(
            "paperwork_backend.sync.pagetracker"
        ).paperwork_dir = openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
            self.tmp_paperwork_dir
        )
        self.core.get_by_name(
            "paperwork_backend.sync.doctracker"
        ).paperwork_dir = openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
            self.tmp_paperwork_dir
        )

        self.pillowed = []

        self.model = self.core.get_by_name("paperwork_backend.model.fake")

        self.core.call_all(Config.config_put, "ocr_langs", ["eng"])

    def tearDown(self):
        shutil.rmtree(self.tmp_paperwork_dir)

    def test_guess_orientation(self):
        self.model.docs = [
            {
                "id": 'some_id',
                "url": 'file:///some_work_dir/some_doc_id',
                "mtime": 12345,
                "labels": [],
                "page_boxes": [],
                "page_imgs": [
                    ("file:///some_image.png", self.test_img)
                ],
            },
        ]

        angle = self.core.call_success(
            OrientationGuesser.guess_page_orientation_by_url,
            'file:///some_work_dir/some_doc_id', 0
        )

        self.assertEqual(angle, 90)
        self.assertEqual(self.pillowed, ['file:///some_image.png'])

    def test_impossible_guess(self):
        self.model.docs = [
            {
                "id": 'some_id',
                "url": 'file:///some_work_dir/some_doc_id',
                "mtime": 12345,
                "labels": [],
                "page_boxes": [],
                "page_imgs": [
                    ("file:///some_image.png", self.test_empty_img)
                ],
            },
        ]

        angle = self.core.call_success(
            OrientationGuesser.guess_page_orientation_by_url,
            'file:///some_work_dir/some_doc_id', 0
        )

        self.assertEqual(angle, None)
        self.assertEqual(self.pillowed, [])
