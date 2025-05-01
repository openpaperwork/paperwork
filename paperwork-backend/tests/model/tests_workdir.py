import datetime
import unittest

import openpaperwork_core

from paperwork_backend.interfaces.doc_storage import DocStorage


class TestWorkdir(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("openpaperwork_core.fs.fake")
        self.core.load("paperwork_backend.model.img")
        self.core.load("paperwork_backend.model.workdir")
        self.core.init()

        self.config = self.core.get_by_name("openpaperwork_core.config.fake")
        self.config.settings = {
            "workdir": "file:///some_work_dir"
        }
        self.fs = self.core.get_by_name("openpaperwork_core.fs.fake")

    def test_storage_get_all_docs(self):
        self.fs.fs = {
            "some_work_dir": {
                "some_doc_a": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                },
                "some_doc_b": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                },
            },
        }

        all_docs = []
        self.core.call_success(DocStorage.storage_get_all_docs, all_docs)
        all_docs.sort()
        self.assertEqual(
            all_docs,
            [
                ("some_doc_a", "file:///some_work_dir/some_doc_a"),
                ("some_doc_b", "file:///some_work_dir/some_doc_b"),
            ]
        )

    def test_storage_get_new_doc(self):
        def now():
            return datetime.datetime(
                year=2019, month=9, day=4, hour=13, minute=27, second=10
            )

        self.fs.fs = {
            "some_work_dir": {
                "20191010_1327_10": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                },
                "20191010_1327_10_1": {
                    "doc.pdf": "put_a_pdf_here",
                },
            },
        }

        (doc_id, doc_url) = self.core.call_success(
            DocStorage.storage_get_new_doc, now_func=now
        )
        self.assertEqual(doc_id, "20190904_1327_10")
        self.assertEqual(doc_url, "file:///some_work_dir/20190904_1327_10")

    def test_storage_get_new_doc_2(self):
        def now():
            return datetime.datetime(
                year=2019, month=9, day=4, hour=13, minute=27, second=10
            )

        self.fs.fs = {
            "some_work_dir": {
                "20190904_1327_10": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                },
                "20190904_1327_10_1": {
                    "doc.pdf": "put_a_pdf_here",
                },
            },
        }

        (doc_id, doc_url) = self.core.call_success(
            DocStorage.storage_get_new_doc, now_func=now
        )
        self.assertEqual(doc_id, "20190904_1327_10_2")
        self.assertEqual(doc_url, "file:///some_work_dir/20190904_1327_10_2")

    def test_rename(self):
        self.fs.fs = {
            "some_work_dir": {
                "20190904_1327_10": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                },
                "20190910_1328_10_1": {
                    "doc.pdf": "put_a_pdf_here",
                },
            },
        }

        self.core.call_all(
            DocStorage.doc_rename_by_url,
            "file:///some_work_dir/20190910_1328_10_1",
            "file:///some_work_dir/20200508_2002_25"
        )

        self.assertEqual(
            self.fs.fs, {
                "some_work_dir": {
                    "20190904_1327_10": {
                        "paper.1.jpg": "put_an_image_here",
                        "paper.2.jpg": "put_an_image_here",
                    },
                    "20200508_2002_25": {
                        "doc.pdf": "put_a_pdf_here",
                    },
                }
            }
        )

    def test_rename2(self):
        self.fs.fs = {
            "some_work_dir": {
                "20190904_1327_10": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                },
                "20190904_1327_10_1": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                },
                "20190910_1328_10_1": {
                    "doc.pdf": "put_a_pdf_here",
                },
            },
        }

        self.core.call_all(
            DocStorage.doc_rename_by_url,
            "file:///some_work_dir/20190910_1328_10_1",
            "file:///some_work_dir/20190904_1327_10"
        )

        self.assertEqual(
            self.fs.fs, {
                "some_work_dir": {
                    "20190904_1327_10": {
                        "paper.1.jpg": "put_an_image_here",
                        "paper.2.jpg": "put_an_image_here",
                    },
                    "20190904_1327_10_1": {
                        "paper.1.jpg": "put_an_image_here",
                        "paper.2.jpg": "put_an_image_here",
                    },
                    "20190904_1327_10_2": {
                        "doc.pdf": "put_a_pdf_here",
                    },
                }
            }
        )
