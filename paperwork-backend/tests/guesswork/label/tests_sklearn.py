import shutil
import tempfile
import unittest

import openpaperwork_core
import openpaperwork_core.fs
import openpaperwork_core.util


class TestLabelGuesser(unittest.TestCase):
    def setUp(self):
        openpaperwork_core.util.reset_singletons()

        self.tmp_bayes_dir = tempfile.mkdtemp(
            prefix="paperwork_backend_labels"
        )

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.sync.doctracker")
        self.core.load("paperwork_backend.guesswork.label.sklearn")

        class FakeModule:
            __name__ = "fake_module"

            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = -9999999

                def fs_exists(s, url):
                    for doc in self.fake_storage.docs:
                        if doc['url'] == url:
                            return True
                    return None

        self.core._load_module("fake_module", FakeModule())
        self.core.init()

        self.core.get_by_name(
            "paperwork_backend.sync.doctracker"
        ).paperwork_dir = openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
            self.tmp_bayes_dir
        )
        self.core.get_by_name(
            "paperwork_backend.guesswork.label.sklearn"
        ).bayes_dir = openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
            self.tmp_bayes_dir
        )
        self.fake_storage = self.core.get_by_name(
            "paperwork_backend.model.fake"
        )

        self.core.call_all("reload_label_guessers")
        self.core.call_all("config_put", "label_guessing_min_features", 1)

    def tearDown(self):
        self.core.call_all("tests_cleanup")
        shutil.rmtree(self.tmp_bayes_dir)

    def test_training(self):
        # ## First training
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'sklearn and Flesch are\nthe best',
                'labels': {("some_label", "#123412341234")},
            },
            {
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': 'Flesch sklearn\nbest',
                'labels': {("some_label", "#123412341234")},
            },
            {
                'id': 'test_doc_3',
                'url': 'file:///somewhere/test_doc_3',
                'mtime': 123,
                'text': 'something else',
                'labels': set(),
            },
            {
                'id': 'some_other_old_doc',
                'url': 'file:///somewhere/new_doc_2',
                'mtime': 123,
                'text': 'something something niet',
                'labels': set(),
            },
        ]

        # make a transaction to indicate that those documents are now in
        # the storage --> it will update the training of bayesian filters.
        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        transactions.sort(key=lambda transaction: -transaction.priority)
        self.assertGreater(len(transactions), 0)

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        # XXX(Jflesch): use upd_doc() so it doesn't try to guess labels
        for transaction in transactions:
            transaction.upd_doc("test_doc")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.upd_doc("test_doc_2")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.upd_doc("test_doc_3")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.upd_doc("some_other_old_doc")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.commit()

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        self.assertEqual(len(self.fake_storage.docs[2]['labels']), 0)
        self.assertEqual(len(self.fake_storage.docs[3]['labels']), 0)

        # ## New docs

        self.fake_storage.docs = [
            {  # old doc
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'sklearn and Flesch are\nthe best',
                'labels': {("some_label", "#123412341234")},
            },
            {  # old doc
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': 'Flesch sklearn\nbest',
                'labels': {("some_label", "#123412341234")},
            },
            {  # old doc
                'id': 'test_doc_3',
                'url': 'file:///somewhere/test_doc_3',
                'mtime': 123,
                'text': 'something else',
                'labels': set(),
            },
            {  # new doc on which we will guess the labels
                'id': 'new_doc',
                'url': 'file:///somewhere/new_doc',
                'mtime': 123,
                'text': 'sklearn and Flesch are\ncamiön',
                'labels': set(),
            },
            {  # new doc on which we will guess the labels
                'id': 'new_doc_2',
                'url': 'file:///somewhere/new_doc_2',
                'mtime': 123,
                'text': 'else something',
                'labels': set(),
            },
            {
                'id': 'some_other_old_doc',
                'url': 'file:///somewhere/new_doc_2',
                'mtime': 123,
                'text': 'something something niet',
                'labels': set(),
            },
        ]

        # make a transaction to make the plugin label_guesser add labels
        # on them.
        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        self.assertGreater(len(transactions), 0)

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.add_doc("new_doc")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.add_doc("new_doc_2")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.commit()

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        self.assertEqual(len(self.fake_storage.docs[4]['labels']), 0)
        self.assertEqual(len(self.fake_storage.docs[3]['labels']), 1)
        self.assertEqual(
            list(self.fake_storage.docs[3]['labels'])[0],
            ("some_label", "#123412341234")
        )

        # ## Upd docs

        self.fake_storage.docs = [
            {  # old doc
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'sklearn and Flesch are\nthe best',
                'labels': {("some_label", "#123412341234")},
            },
            {  # old doc
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': 'Flesch sklearn\nbest',
                'labels': {("some_label", "#123412341234")},
            },
            {  # old doc
                'id': 'test_doc_3',
                'url': 'file:///somewhere/test_doc_3',
                'mtime': 123,
                'text': 'something else',
                'labels': set(),
            },
            {  # new doc on which we will guess the labels
                'id': 'new_doc',
                'url': 'file:///somewhere/new_doc',
                'mtime': 123,
                'text': 'sklearn and Flesch are\ncamiön',
                'labels': {("some_label", "#123412341234")},
            },
            {  # new doc on which we will guess the labels
                'id': 'new_doc_2',
                'url': 'file:///somewhere/new_doc_2',
                'mtime': 123,
                'text': 'camion camion camion',  # accents shouldn't matter
                'labels': set(),
            },
            {
                'id': 'some_other_old_doc',
                'url': 'file:///somewhere/new_doc_2',
                'mtime': 123,
                'text': 'something something niet',
                'labels': set(),
            },
        ]

        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        self.assertGreater(len(transactions), 0)

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.upd_doc("new_doc_2")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.commit()

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        self.assertEqual(len(self.fake_storage.docs[4]['labels']), 0)
        self.assertEqual(len(self.fake_storage.docs[3]['labels']), 1)
        self.assertEqual(
            list(self.fake_storage.docs[3]['labels'])[0],
            ("some_label", "#123412341234")
        )

        # ### del docs

        self.fake_storage.docs = [
            {  # old doc
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'sklearn and Flesch are\nthe best',
                'labels': {("some_label", "#123412341234")},
            },
            {  # old doc
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': 'Flesch sklearn\nbest',
                'labels': {("some_label", "#123412341234")},
            },
            {  # old doc
                'id': 'test_doc_3',
                'url': 'file:///somewhere/test_doc_3',
                'mtime': 123,
                'text': 'something else',
                'labels': set(),
            },
            {
                'id': 'some_other_old_doc',
                'url': 'file:///somewhere/new_doc_2',
                'mtime': 123,
                'text': 'something something niet',
                'labels': set(),
            },
        ]

        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        self.assertGreater(len(transactions), 0)

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.del_doc("new_doc")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.del_doc("new_doc_2")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.commit()

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

    def test_sync(self):
        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'sklearn and Flesch are\nthe best',
                'labels': {("some_label", "#123412341234")},
            },
            {
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': 'Flesch sklearn\nbest',
                'labels': {("some_label", "#123412341234")},
            },
            {
                'id': 'test_doc_3',
                'url': 'file:///somewhere/test_doc_3',
                'mtime': 123,
                'text': 'something else',
                'labels': set(),
            },
        ]

        promises = []
        self.core.call_all('sync', promises)
        promise = promises[0]
        for p in promises[1:]:
            promise = promise.then(p)
        promise.schedule()

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        self.fake_storage.docs = [
            {  # old doc
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'sklearn and Flesch are\nthe best',
                'labels': {("some_label", "#123412341234")},
            },
            {  # old doc
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': 'Flesch sklearn\nbest',
                'labels': {("some_label", "#123412341234")},
            },
            {  # old doc
                'id': 'test_doc_3',
                'url': 'file:///somewhere/test_doc_3',
                'mtime': 123,
                'text': 'something else',
                'labels': set(),
            },
            {  # new doc on which we will guess the labels
                'id': 'new_doc',
                'url': 'file:///somewhere/new_doc',
                'mtime': 123,
                'text': 'sklearn and Flesch are\ncamiön',
                'labels': set(),
            },
            {  # new doc on which we will guess the labels
                'id': 'new_doc_2',
                'url': 'file:///somewhere/new_doc_2',
                'mtime': 123,
                'text': 'something something something',
                'labels': set(),
            }
        ]

        # make a transaction to make the plugin label_guesser add labels
        # on them.
        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        self.assertGreater(len(transactions), 0)

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.add_doc("new_doc")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.add_doc("new_doc_2")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.commit()

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        self.assertEqual(len(self.fake_storage.docs[4]['labels']), 0)
        self.assertEqual(len(self.fake_storage.docs[3]['labels']), 1)
        self.assertEqual(
            list(self.fake_storage.docs[3]['labels'])[0],
            ("some_label", "#123412341234")
        )

    def test_training_no_text_at_all(self):
        # ## First training
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': '',
                'labels': {("some_label", "#123412341234")},
            },
            {
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': '',
                'labels': {("some_label", "#123412341234")},
            },
            {
                'id': 'test_doc_3',
                'url': 'file:///somewhere/test_doc_3',
                'mtime': 123,
                'text': '',
                'labels': set(),
            },
            {
                'id': 'some_other_old_doc',
                'url': 'file:///somewhere/new_doc_2',
                'mtime': 123,
                'text': '',
                'labels': set(),
            },
        ]

        # make a transaction to indicate that those documents are now in
        # the storage --> it will update the training of bayesian filters.
        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        transactions.sort(key=lambda transaction: -transaction.priority)
        self.assertGreater(len(transactions), 0)

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        # XXX(Jflesch): use upd_doc() so it doesn't try to guess labels
        for transaction in transactions:
            transaction.upd_doc("test_doc")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.upd_doc("test_doc_2")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.upd_doc("test_doc_3")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.upd_doc("some_other_old_doc")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.commit()

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        self.assertEqual(len(self.fake_storage.docs[2]['labels']), 0)
        self.assertEqual(len(self.fake_storage.docs[3]['labels']), 0)

        # ## New docs

        self.fake_storage.docs = [
            {  # old doc
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': '',
                'labels': {("some_label", "#123412341234")},
            },
            {  # old doc
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': '',
                'labels': {("some_label", "#123412341234")},
            },
            {  # old doc
                'id': 'test_doc_3',
                'url': 'file:///somewhere/test_doc_3',
                'mtime': 123,
                'text': '',
                'labels': set(),
            },
            {  # new doc on which we will guess the labels
                'id': 'new_doc',
                'url': 'file:///somewhere/new_doc',
                'mtime': 123,
                'text': '',
                'labels': set(),
            },
            {  # new doc on which we will guess the labels
                'id': 'new_doc_2',
                'url': 'file:///somewhere/new_doc_2',
                'mtime': 123,
                'text': '',
                'labels': set(),
            },
            {
                'id': 'some_other_old_doc',
                'url': 'file:///somewhere/new_doc_2',
                'mtime': 123,
                'text': '',
                'labels': set(),
            },
        ]

        # make a transaction to make the plugin label_guesser add labels
        # on them.
        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        self.assertGreater(len(transactions), 0)

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.add_doc("new_doc")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.add_doc("new_doc_2")

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        for transaction in transactions:
            transaction.commit()

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        # guessed labels don't actually matter, it must just not crash
