import os
import unittest

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.pillow import Pillow
import openpaperwork_core
import openpaperwork_core.fs

from paperwork_backend.interfaces.doc_import import ImporterFactory
from paperwork_backend.interfaces.doc_import import ImportListener
from paperwork_backend.interfaces.doc_transactions import AbstractDocTransaction
from paperwork_backend.interfaces.doc_transactions import DocTransactionFactory
import paperwork_backend.docimport


class TestImgImport(unittest.TestCase):
    def setUp(self):
        self.test_img_url = openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "test_img.png"
            )
        )
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)

        self.pillowed = []
        self.add_docs = []
        self.upd_docs = []
        self.nb_commits = 0

        class FakeTransaction(AbstractDocTransaction):
            priority = 0

            def add_doc(s, doc_id):
                self.add_docs.append(doc_id)

            def del_doc(s, doc_id):
                pass

            def upd_doc(s, doc_id):
                self.upd_docs.append(doc_id)

            def unchanged_doc(s, doc_id):
                pass

            def cancel(s):
                pass

            def commit(s):
                self.nb_commits += 1

        class FakeModule:
            __name__ = "fake_module"

            class Plugin(
                openpaperwork_core.PluginBase,
                DocTransactionFactory,
                Fs,
                ImportListener,
                Pillow,
            ):
                PRIORITY = 999999999999999999

                def fs_isdir(s, dir_uri):
                    return not dir_uri.lower().endswith(".png")

                def fs_get_mime(s, file_uri):
                    if s.fs_isdir(file_uri):
                        return "inode/directory"
                    return "image/png"

                def fs_mkdir_p(s, dir_uri):
                    return True

                def fs_safe(self, uri):
                    pass

                def fs_unsafe(self, uri):
                    pass

                def fs_join(self, base, url):
                    pass

                def fs_basename(self, url):
                    pass

                def fs_dirname(self, url):
                    pass

                def fs_hash(self, url):
                    pass

                def fs_open(self, uri, mode='r', **kwargs):
                    pass

                def fs_exists(self, uri):
                    pass

                def fs_listdir(self, uri):
                    pass

                def fs_rename(self, old_uri, new_uri):
                    pass

                def fs_unlink(self, uri, **kwargs):
                    pass

                def fs_rm_rf(self, uri, **kwargs):
                    pass

                def fs_get_mtime(self, uri):
                    pass

                def fs_getsize(self, uri):
                    pass

                def fs_copy(self, old_uri, new_uri):
                    pass

                def fs_copytree(self, old_uri, new_uri):
                    pass

                def fs_recurse(self, parent_uri, dir_included=False):
                    pass

                def fs_hide(self, uri):
                    pass

                def fs_iswritable(self, uri):
                    pass

                def fs_resolve(self, uri):
                    pass

                def fs_mktemp(
                    self, prefix=None, suffix=None, mode='w+b', on_disk=False,
                    **kwargs
                ):
                    pass

                def url_to_pillow(s, file_uri):
                    return "non-null value"

                def pillow_to_url(s, img, dst_uri):
                    self.pillowed.append(dst_uri)
                    return dst_uri

                def url_to_img_size(self, file_url):
                    pass

                def url_to_img_size_promise(self, file_url):
                    pass

                def url_to_pillow_promise(self, file_url):
                    pass

                def on_import_done(s, file_import):
                    self.core.call_all(Mainloop.mainloop_quit_graceful)

                def doc_transaction_start(s, transactions, expected=-1):
                    transactions.append(FakeTransaction())

        self.core.load("fake_module", FakeModule())
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.docimport.img")
        self.core.init()

        self.fake_storage = self.core.get_by_name(
            "paperwork_backend.model.fake"
        )


    def test_import_new_doc(self):
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
            file_uris_to_import=[self.test_img_url]
        )

        importers = []
        self.core.call_all(ImporterFactory.get_importer, importers, file_import)
        self.assertEqual(len(importers), 1)

        promise = importers[0].get_import_promise()
        promise.schedule()

        self.core.call_all(Mainloop.mainloop)

        # see fake storage behaviour
        self.assertEqual(self.pillowed, [
            'file:///some_doc/new_page.jpeg'
        ])
        self.assertEqual(self.add_docs, ['1'])
        self.assertEqual(self.upd_docs, [])
        self.assertEqual(self.nb_commits, 1)

        self.assertEqual(file_import.ignored_files, [])
        self.assertEqual(file_import.imported_files, {self.test_img_url})
        self.assertEqual(file_import.new_doc_ids, {'1'})
        self.assertEqual(file_import.upd_doc_ids, set())
        self.assertEqual(file_import.stats['Images'], 1)
        self.assertEqual(file_import.stats['Documents'], 1)
        self.assertEqual(file_import.stats['Pages'], 0)

    def test_import_upd_doc(self):
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
                'page_boxes': [
                    'some_content_for_page_1',
                    'some_content_for_page_2',
                ]
            },
        ]

        file_import = paperwork_backend.docimport.FileImport(
            file_uris_to_import=[self.test_img_url],
            active_doc_id='test_doc_2'
        )

        importers = []
        self.core.call_all(ImporterFactory.get_importer, importers, file_import)
        self.assertEqual(len(importers), 1)

        promise = importers[0].get_import_promise()
        promise.schedule()

        self.core.call_all(Mainloop.mainloop)

        # see fake storage behaviour
        self.assertEqual(self.pillowed, [
            'file:///some_doc/new_page.jpeg'
        ])
        self.assertEqual(self.add_docs, [])
        self.assertEqual(self.upd_docs, ['test_doc_2'])
        self.assertEqual(self.nb_commits, 1)

        self.assertEqual(file_import.ignored_files, [])
        self.assertEqual(file_import.imported_files, {self.test_img_url})
        self.assertEqual(file_import.new_doc_ids, set())
        self.assertEqual(file_import.upd_doc_ids, {'test_doc_2'})
        self.assertEqual(file_import.stats['Images'], 1)
        self.assertEqual(file_import.stats['Documents'], 0)
        self.assertEqual(file_import.stats['Pages'], 1)
