import shutil
import tempfile
import unittest

import openpaperwork_core
import openpaperwork_core.util


class TestIndex(unittest.TestCase):
    def setUp(self):
        openpaperwork_core.util.reset_singletons()

        self.tmp_index_dir = tempfile.mkdtemp(prefix="paperwork_backend_index")

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.index.whoosh")
        self.core.init()

        self.core.get_by_name("paperwork_backend.index.whoosh").index_dir = (
            'file://' + self.tmp_index_dir
        )

        self.fake_storage = self.core.get_by_name(
            "paperwork_backend.model.fake"
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_index_dir)

    def test_transaction(self):
        results = []
        self.core.call_all("index_search", results, "flesch")
        self.assertEqual(results, [])

        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Whoosh and Flesch are\nthe best',
                'labels': set(),
            }
        ]

        transactions = []
        self.core.call_all('doc_transaction_start', transactions)
        transactions.sort(key=lambda transaction: -transaction.priority)
        for transaction in transactions:
            transaction.add_doc('test_doc')
        for transaction in transactions:
            transaction.commit()

        results = []
        self.core.call_all("index_search", results, "flesch")
        self.assertEqual(
            results, [
                ('test_doc', 'file:///somewhere/test_doc')
            ]
        )

    def test_sync(self):
        results = []
        self.core.call_all("index_search", results, "flesch")
        self.assertEqual(results, [])

        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Whoosh and Flesch are\nthe best',
                'labels': set(),
            }
        ]

        core = self.core

        class FakeModuleToStopMainLoop(object):
            __name__ = "mainloop_stopper"

            class Plugin(openpaperwork_core.PluginBase):
                def on_index_commit_end(self):
                    core.call_all("mainloop_quit_graceful")

        self.core._load_module(
            "mainloop_stopper", FakeModuleToStopMainLoop()
        )
        self.core.init()

        promises = []
        self.core.call_all('sync', promises)
        promise = promises[0]
        for p in promises[1:]:
            promise = promise.then(p)
        promise.schedule()

        self.core.call_one('mainloop')

        results = []
        self.core.call_all("index_search", results, "flesch")
        self.assertEqual(
            results, [
                ('test_doc', 'file:///somewhere/test_doc')
            ]
        )

    def test_suggestion(self):
        results = []
        self.core.call_all("suggestion_get", results, "flesch")
        self.assertEqual(results, [])

        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Whoosh and Flesch are\nthe best',
                'labels': set(),
            }
        ]

        transactions = []
        self.core.call_all('doc_transaction_start', transactions)
        transactions.sort(key=lambda transaction: -transaction.priority)
        for transaction in transactions:
            transaction.add_doc('test_doc')
        for transaction in transactions:
            transaction.commit()

        results = set()
        self.core.call_all("suggestion_get", results, "Whoosh flech best")
        results = list(results)
        results.sort()
        self.assertEqual(
            results, [
                "Whoosh flesch best",
            ]
        )
