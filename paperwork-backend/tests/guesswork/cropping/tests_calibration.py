import os
import shutil
import tempfile
import unittest

import PIL
import PIL.Image

import openpaperwork_core
import openpaperwork_core.fs


class TestCropping(unittest.TestCase):
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
        self.core.load("paperwork_backend.guesswork.cropping.calibration")

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
            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 10000000000

                def pillow_to_url(s, img, url):
                    self.pillowed.append((url, img.size))
                    return url

        self.core._load_module("fake_module", FakeModule())

        self.core.init()

        self.model = self.core.get_by_name("paperwork_backend.model.fake")

    def tearDown(self):
        self.core.call_all("tests_cleanup")
        shutil.rmtree(self.tmp_paperwork_dir)

    def test_transaction(self):
        self.core.call_all(
            "config_put", "scanner_calibration",
            [10, 10, 20, 25]
        )
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
                "page_boxes": [
                    [],
                    [],
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
                "page_boxes": [
                    [],
                    [],
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
        self.assertEqual(self.pillowed[0][1], (10, 15))

    def test_transaction_with_paper_sizes(self):
        self.core.call_all(
            "config_put", "scanner_calibration",
            [10, 10, 20, 25]
        )
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
                "page_paper_sizes": [
                    ("file:///paper.0.jpeg", (256, 256)),
                    ("file:///paper.1.jpeg", (256, 256)),
                ],
                "page_boxes": [
                    [],
                    [],
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
                "page_paper_sizes": [
                    ("file:///paper.0.jpeg", (256, 256)),
                    ("file:///paper.1.jpeg", (256, 256)),
                    ("file:///paper.2.jpeg", (256, 256)),
                ],
                "page_boxes": [
                    [],
                    [],
                ],
            },
        ]

        self.assertEqual(self.pillowed, [])

        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        self.assertNotEqual(transactions, [])
        for t in transactions:
            t.upd_doc('some_doc_with_text')
        for t in transactions:
            t.commit()

        # those pages have paper size defined --> no cropping should happen
        # automatically
        self.assertEqual(self.pillowed, [])

    def test_transaction_with_paper_sizes_2(self):
        self.core.call_all(
            "config_put", "scanner_calibration",
            None
        )
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
                "page_boxes": [
                    [],
                    [],
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
                "page_boxes": [
                    [],
                    [],
                ],
            },
        ]

        self.assertEqual(self.pillowed, [])

        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        self.assertNotEqual(transactions, [])
        for t in transactions:
            t.upd_doc('some_doc_with_text')
        for t in transactions:
            t.commit()

        # No calibration defined in the config --> no cropping
        self.assertEqual(self.pillowed, [])
