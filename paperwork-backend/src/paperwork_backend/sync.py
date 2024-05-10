import datetime
import logging
import time

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)


class BaseTransaction(object):
    def __init__(self, core, total_expected):
        self.core = core
        self.processed = 0
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


def diff_lists(list_old, list_new):
    """
    Returns a dictionary giving the differences between both lists.

    Objects in the list must have 2 attributes:
    - `key`
    - `extra`

    `key` values identify each object in both lists.
    Comparisons are done on `key` + `extra`.

    `list_old` will be unrolled immediately.

    Arguments:
        `list_old` -- [a, b, c, ...]
        `list_new` -- [a, c_modified, d, ...]

    Returns:
        [
            ('same', a.key),
            ('del', b.key),
            ('upd', c.key),
            ('add', d.key),
        ]

        list_old + diff => list_new
    """
    list_old = {obj.key: obj for obj in list_old}
    examined_new = set()

    for obj_new in list_new:
        examined_new.add(obj_new.key)

        if obj_new.key not in list_old:
            yield ('added', obj_new.key)
            continue

        obj_old = list_old[obj_new.key]
        if obj_new.extra != obj_old.extra:
            yield ('updated', obj_new.key)
        else:
            yield ('unchanged', obj_new.key)

    for obj_old in list_old.values():
        if obj_old.key not in examined_new:
            yield ('deleted', obj_old.key)


class StorageDoc(object):
    def __init__(self, core, doc_id, doc_url):
        self.core = core
        self.key = doc_id
        self.doc_url = doc_url

    def get_mtime(self):
        mtime = self.core.call_success("doc_get_mtime_by_url", self.doc_url)
        if mtime is None:
            mtime = 0
        return datetime.datetime.fromtimestamp(mtime)

    extra = property(get_mtime)


class Syncer(object):
    """
    This object allows to compare mtimes progressively. It then calls
    the methods `add_doc`, `del_doc`, `upd_doc` and `commit` on the given
    transaction object.

    Useful to handle calls to 'sync' (see interface 'syncable').
    """
    def __init__(self, core, names, new_all, old_all, transactions):
        self.core = core
        self.names = names
        self.new_all = new_all
        self.old_all = old_all
        self.transactions = transactions
        self.diff_generator = None
        self.start = None
        self.nb_compared = 0

        self.work_dir_id = self.core.call_success("storage_get_id")

    def get_promise(self):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.run
        )

    def run(self):
        self.start = time.time()
        self.diff_generator = diff_lists(self.old_all, self.new_all)

        try:
            for (action, key) in self.diff_generator:

                current_work_dir = self.core.call_success("storage_get_id")
                if self.work_dir_id != current_work_dir:
                    LOGGER.warning(
                        "%s: Work directory has changed during sync."
                        " Cancelling transactions",
                        self.names
                    )
                    for transaction in self.transactions:
                        transaction.cancel()
                    return

                self.nb_compared += 1
                if action != 'unchanged':
                    LOGGER.info("Sync: %s, %s", action, key)
                    for name in self.names:
                        self.core.call_one(
                            "mainloop_schedule", self.core.call_all,
                            "on_sync", name, action, key
                        )
                if action == "added":
                    for transaction in self.transactions:
                        LOGGER.debug(
                            "transaction.add_doc<%s>(%s)",
                            transaction.add_doc, key
                        )
                        transaction.add_doc(key)
                elif action == "updated":
                    for transaction in self.transactions:
                        LOGGER.debug(
                            "transaction.upd_doc<%s>(%s)",
                            transaction.upd_doc, key
                        )
                        transaction.upd_doc(key)
                elif action == "deleted":
                    for transaction in self.transactions:
                        LOGGER.debug(
                            "transaction.del_doc<%s>(%s)",
                            transaction.del_doc, key
                        )
                        transaction.del_doc(key)
                else:
                    for transaction in self.transactions:
                        LOGGER.debug(
                            "transaction.unchanged_doc<%s>(%s)",
                            transaction.unchanged_doc, key
                        )
                        transaction.unchanged_doc(key)

            LOGGER.info("Sync: Committing ...")
            for transaction in self.transactions:
                transaction.commit()
            LOGGER.info("Sync: Committed")
            stop = time.time()
            LOGGER.info(
                "%s: Has compared %d objects in %.3fs",
                self.names, self.nb_compared, stop - self.start
            )
        except Exception as exc:
            LOGGER.error(
                "%s: Fail to sync. Cancelling transactions",
                self.names, exc_info=exc
            )
            for transaction in self.transactions:
                transaction.cancel()


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
        Transactions should never be run in parrallel (even if on the same
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
