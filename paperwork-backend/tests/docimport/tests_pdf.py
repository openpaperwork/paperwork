import os
import unittest
import unittest.mock

import openpaperwork_core
import openpaperwork_core.fs
import paperwork_backend.docimport


class TestPdfImport(unittest.TestCase):
    def setUp(self):
        self.test_doc_url = openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "pdfs",
                "test_doc.pdf"
            )
        )
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)

        self.copies = []
        self.add_docs = []
        self.nb_commits = 0
        self.hash_to_docid = {}

        class FakeTransaction(object):
            priority = 0

            def add_doc(s, doc_id):
                self.add_docs.append(doc_id)

            def unchanged_doc(s, doc_id):
                pass

            def commit(s):
                self.nb_commits += 1

        class FakeModule:
            __name__ = "fake_module"

            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 999999999999999999

                def fs_isdir(s, dir_uri):
                    return not dir_uri.lower().endswith(".pdf")

                def fs_get_mime(s, file_uri):
                    if s.fs_isdir(file_uri):
                        return "inode/directory"
                    return "application/pdf"

                def fs_mkdir_p(s, dir_uri):
                    return True

                def fs_copy(s, src_uri, dst_uri):
                    self.copies.append((src_uri, dst_uri))
                    return dst_uri

                def on_import_done(s, file_import):
                    self.core.call_all("mainloop_quit_graceful")

                def doc_transaction_start(s, transactions, expected=-1):
                    transactions.append(FakeTransaction())

                def fs_hash(s, file_url):
                    if file_url == self.test_doc_url:
                        return "DEADBEEF"
                    return "ABCDEF"

                def index_get_doc_id_by_hash(s, h):
                    if h in self.hash_to_docid:
                        return self.hash_to_docid[h]
                    return None

                def poppler_open(s, file_url, password=None):
                    self.assertIsNone(password)
                    return "something"

        self.core._load_module("fake_module", FakeModule())
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.docimport.pdf")
        self.core.init()

        self.fake_storage = self.core.get_by_name(
            "paperwork_backend.model.fake"
        )

    def test_import_pdf(self):
        self.hash_to_docid = {}
        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Simplebayes and Flesch are\nthe best',
                'labels': {("some_label", "#123412341234")},
            },
            {
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': 'Flesch Simplebayes\nbest',
                'labels': {("some_label", "#123412341234")},
            },
        ]

        file_import = paperwork_backend.docimport.FileImport(
            file_uris_to_import=[self.test_doc_url]
        )

        importers = []
        self.core.call_all("get_importer", importers, file_import)
        self.assertEqual(len(importers), 1)

        self.assertEqual(len(importers[0].get_required_data()), 0)

        promise = importers[0].get_import_promise()
        promise.schedule()

        self.core.call_all("mainloop")

        # see fake storage behaviour
        self.assertEqual(self.copies, [
            (self.test_doc_url, 'file:///some_work_dir/1/doc.pdf')
        ])
        self.assertEqual(self.add_docs, ['1'])
        self.assertEqual(self.nb_commits, 1)

        self.assertEqual(file_import.ignored_files, [])
        self.assertEqual(file_import.imported_files, {self.test_doc_url})
        self.assertEqual(file_import.new_doc_ids, {'1'})
        self.assertEqual(file_import.upd_doc_ids, set())
        self.assertEqual(file_import.stats['PDF'], 1)
        self.assertEqual(file_import.stats['Documents'], 1)

    def test_duplicated_pdf(self):
        self.hash_to_docid = {"DEADBEEF": "some_doc_id"}
        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Simplebayes and Flesch are\nthe best',
                'labels': {("some_label", "#123412341234")},
            },
            {
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': 'Flesch Simplebayes\nbest',
                'labels': {("some_label", "#123412341234")},
            },
        ]

        file_import = paperwork_backend.docimport.FileImport(
            file_uris_to_import=[self.test_doc_url]
        )

        importers = []
        self.core.call_all("get_importer", importers, file_import)
        self.assertEqual(len(importers), 1)

        promise = importers[0].get_import_promise()
        promise.schedule()

        self.core.call_all("mainloop")

        self.assertEqual(self.copies, [])
        self.assertEqual(self.add_docs, [])
        self.assertEqual(self.nb_commits, 1)

        self.assertEqual(file_import.ignored_files, [self.test_doc_url])
        self.assertEqual(file_import.imported_files, set())
        self.assertEqual(file_import.new_doc_ids, set())
        self.assertEqual(file_import.upd_doc_ids, set())
        self.assertNotIn('PDF', file_import.stats)
        self.assertEqual(file_import.stats['Already imported'], 1)


class TestRecursivePdfImport(unittest.TestCase):
    def setUp(self):
        self.test_doc_url = openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "pdfs",
                "test_doc.pdf"
            )
        )
        self.test_dir_url = openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "pdfs",
            )
        )
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)

        self.copies = []
        self.add_docs = []
        self.nb_commits = 0
        self.hash_to_docid = {}

        class FakeTransaction(object):
            priority = 0

            def add_doc(s, doc_id):
                self.add_docs.append(doc_id)

            def unchanged_doc(s, doc_id):
                pass

            def commit(s):
                self.nb_commits += 1

        class FakeModule:
            __name__ = "fake_module"

            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 999999999999999999

                def fs_isdir(s, dir_uri):
                    return not dir_uri.lower().endswith(".pdf")

                def fs_get_mime(s, file_uri):
                    if s.fs_isdir(file_uri):
                        return "inode/directory"
                    return "application/pdf"

                def fs_mkdir_p(self, dir_uri):
                    return True

                def fs_copy(s, src_uri, dst_uri):
                    self.copies.append((src_uri, dst_uri))
                    return dst_uri

                def on_import_done(s, file_import):
                    self.core.call_all("mainloop_quit_graceful")

                def doc_transaction_start(s, transactions, expected=-1):
                    transactions.append(FakeTransaction())

                def fs_hash(s, file_url):
                    if file_url == self.test_doc_url:
                        return "DEADBEEF"
                    return "ABCDEF"

                def index_get_doc_id_by_hash(s, h):
                    if h in self.hash_to_docid:
                        return self.hash_to_docid[h]
                    return None

                def poppler_open(s, file_url, password=None):
                    self.assertIsNone(password)
                    return "something"

        self.core._load_module("fake_module", FakeModule())
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.docimport.pdf")
        self.core.init()

        self.fake_storage = self.core.get_by_name(
            "paperwork_backend.model.fake"
        )

    def test_import_pdf(self):
        self.hash_to_docid = {}
        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Simplebayes and Flesch are\nthe best',
                'labels': {("some_label", "#123412341234")},
            },
            {
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': 'Flesch Simplebayes\nbest',
                'labels': {("some_label", "#123412341234")},
            },
        ]

        file_import = paperwork_backend.docimport.FileImport(
            file_uris_to_import=[self.test_dir_url]
        )

        importers = []
        self.core.call_all("get_importer", importers, file_import)
        self.assertEqual(len(importers), 1)

        promise = importers[0].get_import_promise()
        promise.schedule()

        self.core.call_all("mainloop")

        # see fake storage behaviour
        self.assertEqual(self.copies, [
            (self.test_doc_url, 'file:///some_work_dir/1/doc.pdf')
        ])
        self.assertEqual(self.add_docs, ['1'])
        self.assertEqual(self.nb_commits, 1)

        self.assertEqual(file_import.ignored_files, [])
        self.assertEqual(file_import.imported_files, {self.test_doc_url})
        self.assertEqual(file_import.new_doc_ids, {'1'})
        self.assertEqual(file_import.upd_doc_ids, set())
        self.assertEqual(file_import.stats['PDF'], 1)
        self.assertEqual(file_import.stats['Documents'], 1)

    def test_duplicated_pdf(self):
        self.hash_to_docid = {"DEADBEEF": "some_doc_id"}
        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Simplebayes and Flesch are\nthe best',
                'labels': {("some_label", "#123412341234")},
            },
            {
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': 'Flesch Simplebayes\nbest',
                'labels': {("some_label", "#123412341234")},
            },
        ]

        file_import = paperwork_backend.docimport.FileImport(
            file_uris_to_import=[self.test_dir_url]
        )

        importers = []
        self.core.call_all("get_importer", importers, file_import)
        self.assertEqual(len(importers), 1)

        promise = importers[0].get_import_promise()
        promise.schedule()

        self.core.call_all("mainloop")

        self.assertEqual(self.copies, [])
        self.assertEqual(self.add_docs, [])
        self.assertEqual(self.nb_commits, 1)

        self.assertEqual(file_import.ignored_files, [self.test_doc_url])
        self.assertEqual(file_import.imported_files, set())
        self.assertEqual(file_import.new_doc_ids, set())
        self.assertEqual(file_import.upd_doc_ids, set())
        self.assertNotIn('PDF', file_import.stats)


class TestPasswordPdfImport(unittest.TestCase):
    def setUp(self):
        self.test_doc_url = openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "pdfs",
                "test_password.pdf"
            )
        )
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)

        self.copies = []
        self.add_docs = []
        self.nb_commits = 0
        self.hash_to_docid = {}

        class FakeTransaction(object):
            priority = 0

            def add_doc(s, doc_id):
                self.add_docs.append(doc_id)

            def unchanged_doc(s, doc_id):
                pass

            def commit(s):
                self.nb_commits += 1

        class FakeModule:
            __name__ = "fake_module"

            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 999999999999999999

                def fs_isdir(s, dir_uri):
                    return not dir_uri.lower().endswith(".pdf")

                def fs_get_mime(s, file_uri):
                    if s.fs_isdir(file_uri):
                        return "inode/directory"
                    return "application/pdf"

                def fs_mkdir_p(s, dir_uri):
                    return True

                def fs_copy(s, src_uri, dst_uri):
                    self.copies.append((src_uri, dst_uri))
                    return dst_uri

                def on_import_done(s, file_import):
                    self.core.call_all("mainloop_quit_graceful")

                def doc_transaction_start(s, transactions, expected=-1):
                    transactions.append(FakeTransaction())

                def fs_hash(s, file_url):
                    if file_url == self.test_doc_url:
                        return "DEADBEEF"
                    return "ABCDEF"

                def index_get_doc_id_by_hash(s, h):
                    if h in self.hash_to_docid:
                        return self.hash_to_docid[h]
                    return None

                def poppler_open(s, file_url, password=None):
                    self.assertIsNotNone(password)
                    return "something"

                def fs_open(s, file_url, mode):
                    class FsMock(object):
                        def __enter__(se):
                            return se

                        def __exit__(se, *args, **kwargs):
                            return se

                        def write(se, b):
                            pass

                    return FsMock()

        self.core._load_module("fake_module", FakeModule())
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.docimport.pdf")
        self.core.init()

        self.fake_storage = self.core.get_by_name(
            "paperwork_backend.model.fake"
        )

    def test_import_password_pdf(self):
        self.hash_to_docid = {}
        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Simplebayes and Flesch are\nthe best',
                'labels': {("some_label", "#123412341234")},
            },
            {
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': 'Flesch Simplebayes\nbest',
                'labels': {("some_label", "#123412341234")},
            },
        ]

        file_import = paperwork_backend.docimport.FileImport(
            file_uris_to_import=[self.test_doc_url]
        )

        importers = []
        self.core.call_all("get_importer", importers, file_import)
        self.assertEqual(len(importers), 1)
        self.assertEqual(importers[0].get_required_data(), {
            self.test_doc_url: {"password"}
        })

        promise = importers[0].get_import_promise({
            "password": "test1234",
        })
        promise.schedule()

        self.core.call_all("mainloop")

        # see fake storage behaviour
        self.assertEqual(self.copies, [
            (self.test_doc_url, 'file:///some_work_dir/1/doc.pdf')
        ])
        self.assertEqual(self.add_docs, ['1'])
        self.assertEqual(self.nb_commits, 1)

        self.assertEqual(file_import.ignored_files, [])
        self.assertEqual(file_import.imported_files, {self.test_doc_url})
        self.assertEqual(file_import.new_doc_ids, {'1'})
        self.assertEqual(file_import.upd_doc_ids, set())
        self.assertEqual(file_import.stats['PDF'], 1)
        self.assertEqual(file_import.stats['Documents'], 1)
