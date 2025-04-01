import unittest

import openpaperwork_core


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

        class FakeTransaction(object):
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

            def commit(s):
                self.nb_commits += 1

        class FakeModule(object):
            __name__ = "fake_module"

            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 10000000000

                def on_scan_feed_start(s, scan_id):
                    doc_id = self.core.call_success(
                        "scan2doc_scan_id_to_doc_id", scan_id
                    )
                    self.assertIsNotNone(doc_id)

                def doc_transaction_start(self, transactions, nb_expected=-1):
                    transactions.append(FakeTransaction())

                def fs_exists(self, file_url):
                    if "paper.10" in file_url:
                        return None
                    if "existing" in file_url:
                        return True
                    return None

                def fs_isdir(self, file_url):
                    if "." in file_url:
                        return None
                    return True

                def fs_listdir(self, file_url):
                    if "exist" not in file_url:
                        return None
                    r = [
                        (file_url + "/paper.{}.png".format(x))
                        for x in range(1, 10)
                    ]
                    return r

                def doc_id_to_url(s, doc_id, existing=True):
                    return 'file:///some_existing_doc'

                def storage_get_new_doc(s, *args, **kwargs):
                    return ('new_doc_id', 'file:///new_doc')

                def pillow_to_url(s, img, url):
                    self.pillowed.append(url)
                    return url

        self.core._load_module("fake_module", FakeModule())
        self.core.init()

    def test_scan2doc_new(self):
        def at_the_end(args):
            (doc_id, doc_url) = args
            self.results.append(doc_id)

        promise = self.core.call_success("scan2doc_promise")
        promise.then(at_the_end)
        promise.schedule()

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        self.assertTrue(len(self.results) > 0)
        self.assertEqual(self.transaction_type, "add")
        self.assertEqual(self.pillowed, ['file:///new_doc/paper.1.png'])

    def test_scan2doc_upd(self):
        def at_the_end(args):
            (doc_id, doc_url) = args
            self.results.append(doc_id)

        promise = self.core.call_success(
            "scan2doc_promise",
            doc_id="existing",
            doc_url="file:///some_existing_doc"
        )
        promise.then(at_the_end)
        promise.schedule()

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        self.assertTrue(len(self.results) > 0)
        self.assertEqual(self.transaction_type, "upd")
        self.assertEqual(self.pillowed, [
            'file:///some_existing_doc/paper.10.png'
        ])
