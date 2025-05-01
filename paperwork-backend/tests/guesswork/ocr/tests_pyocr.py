import os
import shutil
import tempfile
import unittest

import PIL
import PIL.Image

from openpaperwork_core.interfaces.config import Config
import openpaperwork_core
import openpaperwork_core.fs

from paperwork_backend.interfaces.data_dir_handler import DataDirHandler
from paperwork_backend.interfaces.doc_transactions import DocTransactionFactory
from paperwork_backend.interfaces.ocr import Ocr


class TestPyocr(unittest.TestCase):
    def setUp(self):
        self.tmp_paperwork_dir = tempfile.mkdtemp(
            prefix="paperwork_backend_tests"
        )

        self.test_img = PIL.Image.open(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "test_img.png"
            )
        )

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)

        class FakeModule:
            __name__ = "fake_module"

            class Plugin(
                openpaperwork_core.PluginBase,
                DataDirHandler,
            ):
                PRIORITY = 999999999999999999999

                def data_dir_handler_get_individual_data_dir(s):
                    return openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
                        self.tmp_paperwork_dir
                    )

        self.core.load("fake_module", FakeModule)
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.sync.doctracker")
        self.core.load("paperwork_backend.sync.pagetracker")
        self.core.load("paperwork_backend.guesswork.ocr.pyocr")
        self.core.init()

        self.model = self.core.get_by_name("paperwork_backend.model.fake")

        self.core.call_all(Config.config_put, "ocr_langs", ["eng"])

    def tearDown(self):
        shutil.rmtree(self.tmp_paperwork_dir)

    def test_ocr(self):
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
                "page_hashes": [
                    ("file:///some_image.png", 0),
                ]
            },
        ]

        self.core.call_all(
            Ocr.ocr_page_by_url, "file:///some_work_dir/some_doc_id", page_idx=0
        )

        self.assertNotEqual(len(self.model.docs[0]['page_boxes']), 0)
        self.assertEqual(
            self.model.docs[0]['text'],
            "This is a test\n"
            "image created\n"
            "by Flesch\n"
        )

    def test_transaction(self):
        self.model.docs = [
            {
                "id": 'some_doc_with_text',
                "url": 'file:///some_work_dir/some_doc_id',
                "mtime": 12345,
                "labels": [],
                "page_boxes": [
                    # Should be list of LineBoxes, but meh.
                    "putsomething",
                    "here"
                ],
                "page_imgs": [
                    ("file:///paper.0.png", None),
                    ("file:///paper.1.png", None),
                ],
                "page_hashes": [
                    ("file:///paper.0.png", 0),
                    ("file:///paper.1.png", 1),
                ],
            },
            {
                "id": 'some_doc',
                "url": 'file:///some_work_dir/some_2',
                "mtime": 12345,
                "labels": [],
                "page_boxes": [],
                "page_imgs": [
                    ("file:///some_image.png", self.test_img)
                ],
                "page_hashes": [
                    ("file:///some_image.png", 3),
                ],
            },
        ]

        transactions = []
        self.core.call_all(DocTransactionFactory.doc_transaction_start, transactions)
        transactions.sort(key=lambda transaction: -transaction.priority)
        self.assertNotEqual(transactions, [])

        for t in transactions:
            t.add_doc('some_doc_with_text')
        for t in transactions:
            t.add_doc('some_doc')
        for t in transactions:
            t.commit()

        # first doc already had boxes --> no boxes or text added
        self.assertNotIn('text', self.model.docs[0])
        self.assertEqual(self.model.docs[0]['page_boxes'], [
            "putsomething", "here"  # unchanged
        ])

        # but OCR should be run on the other doc
        self.assertNotEqual(len(self.model.docs[1]['page_boxes']), 0)
        self.assertEqual(
            self.model.docs[1]['text'],
            "This is a test\n"
            "image created\n"
            "by Flesch\n"
        )

    def test_tricky(self):
        self.model.docs = [
            {
                "id": 'some_doc_with_text',
                "url": 'file:///some_work_dir/some_doc_id',
                "mtime": 12345,
                "labels": [],
                "page_boxes": [
                    # Should be list of LineBoxes, but meh.
                    "putsomething",
                    "here"
                ],
                "page_imgs": [
                    ("file:///paper.0.png", self.test_img),
                    ("file:///paper.1.png", self.test_img),
                ],
                "page_hashes": [
                    ("file:///paper.0.png", 0),
                    ("file:///paper.1.png", 1),
                ],
            },
        ]

        transactions = []
        self.core.call_all(DocTransactionFactory.doc_transaction_start, transactions)
        self.assertNotEqual(transactions, [])
        for t in transactions:
            t.add_doc('some_doc_with_text')
        for t in transactions:
            t.commit()

        # first doc already had boxes --> no boxes or text added
        self.assertNotIn('text', self.model.docs[0])
        self.assertEqual(self.model.docs[0]['page_boxes'], [
            "putsomething", "here"  # unchanged
        ])

        self.model.docs = [
            {
                "id": 'some_doc_with_text',
                "url": 'file:///some_work_dir/some_doc_id',
                "mtime": 12346,
                "labels": [],
                "page_boxes": [],
                "page_imgs": [
                    ("file:///paper.0.png", self.test_img),  # new page
                    ("file:///paper.1.png", self.test_img),
                    ("file:///paper.2.png", self.test_img),  # modified
                ],
                "page_hashes": [
                    ("file:///paper.0.png", 0xDEADBEEF),  # new page
                    ("file:///paper.1.png", 0),
                    ("file:///paper.2.png", 0xBEEFDEAD),  # modified
                ],
            },
        ]

        transactions = []
        self.core.call_all(DocTransactionFactory.doc_transaction_start, transactions)
        self.assertNotEqual(transactions, [])
        for t in transactions:
            t.upd_doc('some_doc_with_text')
        for t in transactions:
            t.commit()

        self.assertNotEqual(len(self.model.docs[0]['page_boxes']), 0)
        self.assertEqual(
            self.model.docs[0]['text'],
            "This is a test\n"  # new page
            "image created\n"  # new page
            "by Flesch\n"  # new page
            "\n\n"
            # unchanged page --> no OCR
            "\n\n"
            "This is a test\n"  # modified page
            "image created\n"  # modified page
            "by Flesch\n"  # modified page
        )
