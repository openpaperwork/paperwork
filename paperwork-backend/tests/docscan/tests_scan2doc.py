import unittest

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.pillow import Pillow
import openpaperwork_core

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_transactions import AbstractDocTransaction
from paperwork_backend.interfaces.doc_transactions import DocTransactionFactory
from paperwork_backend.interfaces.scan import ScanListener
from paperwork_backend.interfaces.scan2doc import Scan2Doc


class TestScan2Doc(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.fs.fake")
        self.core.init()
        self.fs = self.core.get_by_name("openpaperwork_core.fs.fake")

        self.core.load("paperwork_backend.docscan.fake")
        self.core.load("paperwork_backend.docscan.scan2doc")

        self.results = []
        self.pillowed = []
        self.transaction_type = None
        self.nb_commits = 0

        class FakeTransaction(AbstractDocTransaction):
            priority = 0

            def add_doc(s, doc_id):
                self.assertIsNone(self.transaction_type)
                self.transaction_type = "add"

            def upd_doc(s, doc_id):
                self.assertIsNone(self.transaction_type)
                self.transaction_type = "upd"

            def del_doc(s, doc_id):
                pass

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
                DocStorage,
                DocTransactionFactory,
                Fs,
                Pillow,
                ScanListener,
            ):
                PRIORITY = 10000000000

                def storage_get_name(self):
                    pass

                def on_scan_feed_start(s, scan_id):
                    doc_id = self.core.call_success(
                        Scan2Doc.scan2doc_scan_id_to_doc_id, scan_id
                    )
                    self.assertIsNotNone(doc_id)

                def on_scan_page_start(self, scan_id, page_nb, scan_params):
                    pass

                def on_scan_started(self, scan_id):
                    pass

                def on_scan_chunk(self, scan_id, scan_params, img_chunk):
                    pass

                def on_scan_page_end(self, scan_id, page_nb, img):
                    pass

                def on_scan_feed_end(self, scan_id):
                    pass

                def doc_transaction_start(s, transactions, nb_expected=-1):
                    transactions.append(FakeTransaction())

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

                def fs_mkdir_p(self, uri):
                    pass

                def fs_recurse(self, parent_uri, dir_included=False):
                    pass

                def fs_hide(self, uri):
                    pass

                def fs_get_mime(self, uri):
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

                def fs_exists(s, file_url):
                    if "paper.10" in file_url:
                        return None
                    if "existing" in file_url:
                        return True
                    return None

                def fs_isdir(s, file_url):
                    if "." in file_url:
                        return None
                    return True

                def fs_listdir(s, file_url):
                    if "exist" not in file_url:
                        return None
                    r = [
                        (file_url + "/paper.{}.png".format(x))
                        for x in range(1, 10)
                    ]
                    return r

                def doc_id_to_url(s, doc_id, existing=True):
                    return 'file:///some_existing_doc'

                def doc_url_to_id(self, doc_url):
                    pass

                def doc_get_date_by_id(self, doc_id):
                    pass

                def doc_get_id_by_date(self, date):
                    pass

                def storage_get_id(self):
                    pass

                def storage_get_all_docs(self, out: list, only_valid=True):
                    pass

                def storage_delete_doc_id(self, doc_id, trash=True):
                    pass

                def doc_rename_by_url(self, src_doc_url, dst_doc_url):
                    pass

                def doc_copy_by_url(self, src_doc_url):
                    pass

                def doc_get_size_by_url(self, doc_url):
                    pass

                def storage_get_new_doc(s, *args, **kwargs):
                    return ('new_doc_id', 'file:///new_doc')

                def url_to_img_size(self, file_url):
                    pass

                def url_to_img_size_promise(self, file_url):
                    pass

                def url_to_pillow(self, file_url):
                    pass

                def url_to_pillow_promise(self, file_url):
                    pass

                def pillow_to_url(s, img, url):
                    self.pillowed.append(url)
                    return url

        self.core.load("fake_module", FakeModule())
        self.core.init()

    def test_scan2doc_new(self):
        def at_the_end(args):
            (doc_id, doc_url) = args
            self.results.append(doc_id)

        promise = self.core.call_success(Scan2Doc.scan2doc_promise)
        promise.then(at_the_end)
        promise.schedule()

        self.core.call_all(Mainloop.mainloop_quit_graceful)
        self.core.call_one(Mainloop.mainloop)

        self.assertTrue(len(self.results) > 0)
        self.assertEqual(self.transaction_type, "add")
        self.assertEqual(self.pillowed, ['file:///new_doc/paper.1.png'])

    def test_scan2doc_upd(self):
        def at_the_end(args):
            (doc_id, doc_url) = args
            self.results.append(doc_id)

        promise = self.core.call_success(
            Scan2Doc.scan2doc_promise,
            doc_id="existing",
            doc_url="file:///some_existing_doc"
        )
        promise.then(at_the_end)
        promise.schedule()

        self.core.call_all(Mainloop.mainloop_quit_graceful)
        self.core.call_one(Mainloop.mainloop)

        self.assertTrue(len(self.results) > 0)
        self.assertEqual(self.transaction_type, "upd")
        self.assertEqual(self.pillowed, [
            'file:///some_existing_doc/paper.10.png'
        ])
