import os
import os.path
import shutil
import tempfile
import unittest

import openpaperwork_core
import paperwork_backend.sync


class TestConvertedPdf(unittest.TestCase):
    def setUp(self):
        self.test_doc = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "test.docx"
        )
        self.upd_docs = set()
        self.nb_commits = 0

        class TestTransaction(paperwork_backend.sync.BaseTransaction):
            priority = 0

            def upd_doc(s, doc_id):
                super().upd_doc(doc_id)
                self.upd_docs.add(doc_id)

            def commit(s):
                super().commit()
                self.nb_commits += 1

        class FakeModule(object):
            __name__ = "fake_module"

            class Plugin(openpaperwork_core.PluginBase):
                def doc_transaction_start(s, transactions, expected=-1):
                    transactions.append(TestTransaction(
                        self.core, expected
                    ))

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core._load_module("fake_module", FakeModule())
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("paperwork_backend.model.converted")
        self.core.init()

        self.config = self.core.get_by_name("openpaperwork_core.config.fake")

    def test_on_page_get_img_url(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.config.settings = {
                "workdir": self.core.call_success("fs_safe", tmp_dir),
            }

            doc_dir = os.path.join(tmp_dir, "some_doc")
            os.makedirs(doc_dir)
            docx = os.path.join(doc_dir, "doc.docx")
            pdf = os.path.join(doc_dir, "doc.pdf")

            shutil.copyfile(self.test_doc, docx)

            self.core.call_all(
                "page_get_img_url",
                self.core.call_success("fs_safe", doc_dir),
                0,  # page_idx
                write=False
            )

            self.core.call_all("mainloop_quit_graceful")
            self.core.call_one("mainloop")

            self.assertEqual(self.nb_commits, 1)
            self.assertTrue(os.access(pdf, os.R_OK))

    def test_sync(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.config.settings = {
                "workdir": self.core.call_success("fs_safe", tmp_dir),
            }

            doc_dir = os.path.join(tmp_dir, "some_doc")
            os.makedirs(doc_dir)
            docx = os.path.join(doc_dir, "doc.docx")
            pdf = os.path.join(doc_dir, "doc.pdf")

            shutil.copyfile(self.test_doc, docx)

            self.core.call_all("transaction_sync_all")

            self.core.call_all("mainloop_quit_graceful")
            self.core.call_one("mainloop")

            self.assertTrue(os.access(pdf, os.R_OK))
