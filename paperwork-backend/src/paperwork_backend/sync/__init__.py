import logging

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)


class BaseTransaction:
    def __init__(self, core, total_expected):
        self.core = core
        self.processed = 0
        self.priority = 0
        self.total = total_expected
        self._current_doc = None
        self._current_doc_pages = -1

    def notify_progress(
            self, upd_type, description, page_nb=-1, total_pages=-1):
        if self.total <= self.processed:
            self.total = self.processed + 1
        if self.total <= 0:
            progression = 0
        else:
            progression = self.processed / self.total

        if page_nb >= 0 and total_pages > 0:
            progression += (page_nb / total_pages / self.total)

        self.core.call_one(
            "mainloop_schedule", self.core.call_all,
            "on_progress", upd_type, progression, description
        )

    def notify_done(self, upd_type):
        self.core.call_one(
            "mainloop_schedule", self.core.call_all,
            "on_progress", upd_type, 1.0
        )

    def add_doc(self, doc_id):
        self._current_doc = doc_id
        self._current_doc_pages = -1
        self.processed += 1

    def upd_doc(self, doc_id):
        self._current_doc = doc_id
        self._current_doc_pages = -1
        self.processed += 1

    def del_doc(self, doc_id):
        self._current_doc = doc_id
        self._current_doc_pages = -1
        self.processed += 1

    def unchanged_doc(self, doc_id):
        self.processed += 1

    def cancel(self):
        self._current_doc = None
        self._current_doc_pages = -1

    def commit(self):
        self._current_doc = None


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 20000

    def get_interfaces(self):
        return ['transaction_manager']

    def get_deps(self):
        return [
            {
                'interface': 'work_queue',
                'defaults': ['openpaperwork_core.work_queue.default'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.core.call_all("work_queue_create", "transactions")

    def transaction_schedule(self, promise):
        """
        Transactions should never be run in parallel (even if on the same
        thread). Some databases (Sqlite3) don't support that.
        --> we use a work queue to ensure they are run one after the other.
        """
        return self.core.call_success(
            "work_queue_add_promise", "transactions", promise
        )

    def _transaction_simple(self, changes):
        if len(changes) <= 0:
            LOGGER.info("No change. Nothing to do")
            return

        transactions = []
        self.core.call_all("doc_transaction_start", transactions, len(changes))
        transactions.sort(key=lambda transaction: -transaction.priority)

        try:
            for (change, doc_id) in changes:
                doc_url = self.core.call_success("doc_id_to_url", doc_id)
                if doc_url is None:
                    change = 'del'
                elif self.core.call_success("is_doc", doc_url) is None:
                    change = 'del'
                for transaction in transactions:
                    if change == 'add':
                        transaction.add_doc(doc_id)
                    elif change == 'upd':
                        transaction.upd_doc(doc_id)
                    elif change == 'del':
                        transaction.del_doc(doc_id)
                    else:
                        raise Exception("Unknown change type: %s" % change)

            for transaction in transactions:
                transaction.commit()
        except Exception as exc:
            LOGGER.error("Transactions have failed", exc_info=exc)
            for transaction in transactions:
                transaction.cancel()
            raise

    def transaction_simple_promise(self, changes):
        """
        See transaction_simple(). Must be scheduled with
        'transaction_schedule()'.
        """
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self._transaction_simple, args=(changes,)
        )

    def transaction_simple(self, changes: list):
        """
        Helper method.
        Schedules a transaction for a bunch of document ids.

        Changes must be a list:
        [
            ('add', 'some_doc_id'),
            ('upd', 'some_doc_id_2'),
            ('upd', 'some_doc_id_3'),
            ('del', 'some_doc_id_4'),
        ]
        """
        return self.transaction_schedule(
            self.core.call_success("transaction_simple_promise", changes)
        )

    def transaction_sync_all(self):
        """
        Make sure all the plugins synchronize their databases with the work
        directory.
        """
        promises = []
        self.core.call_all("sync", promises)
        promise = promises[0]
        for p in promises[1:]:
            promise = promise.then(p)
        self.transaction_schedule(promise)
