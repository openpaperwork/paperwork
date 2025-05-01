import shutil
import tempfile
import unittest

from openpaperwork_core.interfaces.mainloop import Mainloop
import openpaperwork_core
import openpaperwork_core.util

from paperwork_backend.interfaces.doc_transactions import DocTransactionFactory
from paperwork_backend.interfaces.index import Index
from paperwork_backend.interfaces.index import IndexListener
from paperwork_backend.interfaces.suggestions import SuggestionProvider
from paperwork_backend.interfaces.sync import Syncable


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
        self.core.call_all(Index.index_search, results, "flesch")
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
        self.core.call_all(DocTransactionFactory.doc_transaction_start, transactions)
        transactions.sort(key=lambda transaction: -transaction.priority)
        for transaction in transactions:
            transaction.add_doc('test_doc')
        for transaction in transactions:
            transaction.commit()

        results = []
        self.core.call_all(Index.index_search, results, "flesch")
        self.assertEqual(
            results, [
                ('test_doc', 'file:///somewhere/test_doc')
            ]
        )

    def test_sync(self):
        results = []
        self.core.call_all(Index.index_search, results, "flesch")
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

        class FakeModuleToStopMainLoop:
            __name__ = "mainloop_stopper"

            class Plugin(
                openpaperwork_core.PluginBase,
                IndexListener
            ):
                def on_index_cancel(s):
                    pass

                def on_index_updated(s):
                    pass

                def on_index_commit_start(s):
                    pass

                def on_index_commit_end(s):
                    core.call_all(Mainloop.mainloop_quit_graceful)

        self.core.load(
            "mainloop_stopper", FakeModuleToStopMainLoop()
        )
        self.core.init()

        promises = []
        self.core.call_all(Syncable.sync, promises)
        promise = promises[0]
        for p in promises[1:]:
            promise = promise.then(p)
        promise.schedule()

        self.core.call_one(Mainloop.mainloop)

        results = []
        self.core.call_all(Index.index_search, results, "flesch")
        self.assertEqual(
            results, [
                ('test_doc', 'file:///somewhere/test_doc')
            ]
        )

    def test_suggestion(self):
        results = []
        self.core.call_all(SuggestionProvider.suggestion_get, results, "flesch")
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
        self.core.call_all(DocTransactionFactory.doc_transaction_start, transactions)
        transactions.sort(key=lambda transaction: -transaction.priority)
        for transaction in transactions:
            transaction.add_doc('test_doc')
        for transaction in transactions:
            transaction.commit()

        results = set()
        self.core.call_all(SuggestionProvider.suggestion_get, results, "Whoosh flech best")
        results = list(results)
        results.sort()
        self.assertEqual(
            results, [
                "Whoosh flesch best",
            ]
        )
