import os
import tempfile
import unittest

import paperwork_backend.docimport
import paperwork_backend.sync
import openpaperwork_core


class TestConvertedImport(unittest.TestCase):
    def setUp(self):
        self.test_doc = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "test.docx"
        )

        self.add_docs = set()
        self.upd_docs = set()
        self.nb_commits = 0

        class TestTransaction(paperwork_backend.sync.BaseTransaction):
            priority = 0

            def add_doc(s, doc_id):
                super().add_doc(doc_id)
                self.add_docs.add(doc_id)

            def upd_doc(s, doc_id):
                super().upd_doc(doc_id)
                self.upd_docs.add(doc_id)

            def commit(s):
                super().commit()
                self.nb_commits += 1

        class FakeModule:
            __name__ = "fake_module"

            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 999999999999999999

                def doc_transaction_start(s, transactions, expected=-1):
                    transactions.append(TestTransaction(
                        self.core, expected
                    ))

                def index_get_doc_id_by_hash(s, h):
                    all_docs = []
                    self.core.call_success("storage_get_all_docs", all_docs)
                    for (doc_id, doc_url) in all_docs:
                        doc_h = self.core.call_success(
                            "doc_get_hash_by_url", doc_url
                        )
                        if doc_h == h:
                            return doc_id
                    return None

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core._load_module("fake_module", FakeModule())
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("paperwork_backend.docimport.converted")
        self.core.init()

        self.config = self.core.get_by_name("openpaperwork_core.config.fake")

    def test_import_docx(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.config.settings = {
                "workdir": self.core.call_success("fs_safe", tmp_dir),
            }

            file_to_import = self.core.call_success("fs_safe", self.test_doc)

            file_import = paperwork_backend.docimport.FileImport(
                file_uris_to_import=[file_to_import]
            )

            importers = []
            self.core.call_all("get_importer", importers, file_import)
            self.assertEqual(len(importers), 1)

            promise = importers[0].get_import_promise()
            promise.schedule()

            self.core.call_all("mainloop_quit_graceful")
            self.core.call_one("mainloop")

            self.assertEqual(len(self.add_docs), 1)
            self.assertEqual(self.nb_commits, 1)

            self.assertEqual(file_import.ignored_files, [])
            self.assertEqual(file_import.imported_files, {file_to_import})
            self.assertEqual(len(file_import.new_doc_ids), 1)
            self.assertEqual(file_import.upd_doc_ids, set())
            self.assertEqual(file_import.stats['Microsoft Word (.docx)'], 1)
            self.assertEqual(file_import.stats['Documents'], 1)

            self.assertIsNotNone(
                self.core.call_success(
                    "fs_join",
                    self.core.call_success(
                        "doc_id_to_url", list(file_import.new_doc_ids)[0]
                    ),
                    "doc.pdf"
                )
            )

    def test_import_duplicated_docx(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.config.settings = {
                "workdir": self.core.call_success("fs_safe", tmp_dir),
            }
            file_to_import = self.core.call_success("fs_safe", self.test_doc)

            # 1st import
            file_import = paperwork_backend.docimport.FileImport(
                file_uris_to_import=[file_to_import]
            )

            importers = []
            self.core.call_all("get_importer", importers, file_import)
            self.assertEqual(len(importers), 1)

            promise = importers[0].get_import_promise()
            promise.schedule()

            self.core.call_all("mainloop_quit_graceful")
            self.core.call_one("mainloop")

            self.assertEqual(len(self.add_docs), 1)
            self.assertEqual(self.nb_commits, 1)

            self.assertEqual(file_import.ignored_files, [])
            self.assertEqual(file_import.imported_files, {file_to_import})
            self.assertEqual(len(file_import.new_doc_ids), 1)
            self.assertEqual(file_import.upd_doc_ids, set())
            self.assertEqual(file_import.stats['Microsoft Word (.docx)'], 1)
            self.assertEqual(file_import.stats['Documents'], 1)

            self.assertIsNotNone(
                self.core.call_success(
                    "fs_join",
                    self.core.call_success(
                        "doc_id_to_url", list(file_import.new_doc_ids)[0]
                    ),
                    "doc.pdf"
                )
            )

            # 2nd import
            file_import = paperwork_backend.docimport.FileImport(
                file_uris_to_import=[file_to_import]
            )

            importers = []
            self.core.call_all("get_importer", importers, file_import)
            self.assertEqual(len(importers), 1)

            promise = importers[0].get_import_promise()
            promise.schedule()

            self.core.call_all("mainloop_quit_graceful")
            self.core.call_one("mainloop")

            self.assertEqual(len(self.add_docs), 1)
            self.assertEqual(self.nb_commits, 2)

            self.assertEqual(file_import.ignored_files, [file_to_import])
            self.assertEqual(file_import.imported_files, set())
            self.assertEqual(file_import.new_doc_ids, set())
            self.assertEqual(file_import.upd_doc_ids, set())
            self.assertNotIn('Microsoft Word (.docx)', file_import.stats)
            self.assertEqual(file_import.stats['Already imported'], 1)
