import os
import shutil
import tempfile
import unittest

import PIL
import PIL.Image

import openpaperwork_core
import openpaperwork_core.fs


class TestAce(unittest.TestCase):
    def setUp(self):
        self.tmp_paperwork_dir = tempfile.mkdtemp(
            prefix="paperwork_backend_tests"
        )

        self.test_img = PIL.Image.open(
            "{}/test_img.jpeg".format(
                os.path.dirname(os.path.abspath(__file__))
            )
        )

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.sync.doctracker")
        self.core.load("paperwork_backend.sync.pagetracker")
        self.core.load("paperwork_backend.guesswork.color.libpillowfight")
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

        class FakeModule(object):
            __name__ = "fake_module"

            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 10000000000

                def pillow_to_url(s, img, url):
                    average_color = self._compute_average_color(img)
                    self.pillowed.append((url, average_color))
                    return url

        self.core._load_module("fake_module", FakeModule())

        self.core.init()

        self.model = self.core.get_by_name("paperwork_backend.model.fake")

    def tearDown(self):
        self.core.call_all("tests_cleanup")
        shutil.rmtree(self.tmp_paperwork_dir)

    def _compute_average_color(self, img):
        img = img.resize(
            (1, 1),
            getattr(PIL.Image, 'Resampling', PIL.Image).LANCZOS
        )
        return img.getpixel((0, 0))

    def test_transaction(self):
        self.model.docs = [
            {
                "id": 'some_doc_with_text',
                "url": 'file:///some_work_dir/some_doc_id',
                "mtime": 12345,
                "labels": [],
                "page_imgs": [
                    ("file:///paper.0.jpeg", None),
                    ("file:///paper.1.jpeg", None),
                ],
                "page_hashes": [
                    ("file:///paper.0.jpeg", 0),
                    ("file:///paper.1.jpeg", 1),
                ],
            },
        ]

        promises = []
        self.core.call_all("sync", promises)

        for promise in promises:
            promise.schedule()

        self.core.call_success(
            "mainloop_schedule", self.core.call_all, "mainloop_quit_graceful"
        )
        self.core.call_one("mainloop")

        self.assertEqual(self.pillowed, [])

        self.model.docs = [
            {
                "id": 'some_doc_with_text',
                "url": 'file:///some_work_dir/some_doc_id',
                "mtime": 12345,
                "labels": [],
                "page_imgs": [
                    ("file:///paper.0.jpeg", None),
                    ("file:///paper.1.jpeg", None),
                    ("file:///paper.2.jpeg", self.test_img),
                ],
                "page_hashes": [
                    ("file:///paper.0.jpeg", 0),
                    ("file:///paper.1.jpeg", 1),
                    ("file:///paper.2.jpeg", 2),
                ],
            },
        ]

        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        transactions.sort(key=lambda transaction: -transaction.priority)
        self.assertNotEqual(transactions, [])
        for t in transactions:
            t.upd_doc('some_doc_with_text')
        for t in transactions:
            t.commit()

        self.assertEqual(len(self.pillowed), 1)
        self.assertEqual(self.pillowed[0][0], "file:///paper.2.jpeg")
        # algorithm may make the results vary if it changes later, but we can
        # still check that it actually changed the average color of the
        # document
        self.assertNotEqual(
            self._compute_average_color(self.test_img),
            self.pillowed[0][1]
        )
