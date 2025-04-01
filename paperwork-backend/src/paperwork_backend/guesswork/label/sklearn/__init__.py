"""
Label guesser guesses label based on document text and bayes filters.
It adds the guessed labels on new documents (in other words, freshly
added documents).

It stores data in 2 ways:
- sklearn pickling of TfidVectorizer
- sqlite database
"""
import importlib
import logging
import sqlite3
import threading

import openpaperwork_core
import openpaperwork_core.promise
import openpaperwork_core.util


LOGGER = logging.getLogger(__name__)
CREATE_TABLES = [
    # we could use the labels file instead, but some people access their work
    # directory through very slow Internet connections, so we better
    # keep a copy in the DB.
    (
        "CREATE TABLE IF NOT EXISTS labels ("
        " doc_id TEXT NOT NULL,"
        " label TEXT NOT NULL,"
        " PRIMARY KEY (doc_id, label)"
        ")"
    ),
    (  # see sklearn.feature_extraction.text.CountVectorizer.vocabulary
        "CREATE TABLE IF NOT EXISTS vocabulary ("
        " word TEXT NOT NULL,"
        " feature INTEGER NOT NULL,"
        " PRIMARY KEY (feature)"
        " UNIQUE (word)"
        ")"
    ),
    (
        "CREATE TABLE IF NOT EXISTS features ("
        " doc_id TEXT NOT NULL,"
        " vector NUMPY_ARRAY NOT NULL,"
        " PRIMARY KEY (doc_id)"
        ")"
    )
]


class PluginConfig(object):
    SETTINGS = {  # settings --> default value
        'batch_size': 200,
        # Limit the number of words used for performance reasons
        'max_words': 15000,
        # Limit the number of documents used for performance reasons
        # backlog is the number of required documents with and without each
        # label
        'max_doc_backlog': 100,
        'max_time': 10,  # seconds

        # if the document contains too few words, the classifiers tend to
        # put every possible labels on it. --> we ignore documents with too
        # few words / features.
        'min_features': 10,
    }

    def __init__(self, core):
        self.core = core

    def register(self):
        class Setting(object):
            def __init__(s, setting, default_val):
                s.setting = setting
                s.default_val = default_val

            def register(s):
                setting = self.core.call_success(
                    "config_build_simple", "label_guessing",
                    s.setting, lambda: s.default_val
                )
                self.core.call_all(
                    "config_register", "label_guessing_" + s.setting, setting
                )

        for (setting, default_val) in self.SETTINGS.items():
            Setting(setting, default_val).register()

    def get(self, key):
        return self.core.call_success("config_get", "label_guessing_" + key)


class Plugin(
            openpaperwork_core.PluginBase,
            metaclass=openpaperwork_core.util.Singleton
        ):
    PRIORITY = 100

    @classmethod
    def get_interfaces(cls):
        return [
            'sync',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'data_dir_handler',
                'defaults': ['paperwork_backend.datadirhandler'],
            },
            {
                'interface': 'data_versioning',
                'defaults': ['openpaperwork_core.data_versioning'],
            },
            {
                'interface': 'doc_labels',
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                'interface': 'doc_tracking',
                'defaults': ['paperwork_backend.sync.doctracker'],
            },
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'sqlite',
                'defaults': ['openpaperwork_core.sqlite'],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
            {
                'interface': 'work_queue',
                'defaults': ['openpaperwork_core.work_queue.default'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)

        self.bayes = None
        self.config = None

        # If we load the classifiers, we keep the vectorizer that goes with
        # them, because the vectorizer must return vectors that have the size
        # that the classifiers expect. If we would train the vectorizer with
        # new documents, the vector sizes could increase
        # Since loading the classifiers is a fairly long operations, we only
        # do it when we actually need them.
        self.word_reductor = None
        self.classifiers = None
        self.vectorizer = None

        # indicates whether the classifiers have been / are
        # been loaded
        self.classifiers_loaded = False

        # Do NOT use an RLock() here: The transaction locks this mutex
        # until commit() (or cancel()) is called. However, add_doc(),
        # del_doc(), upd_doc() and commit() may be called from different
        # threads.
        self.classifiers_cond = threading.Condition(threading.Lock())

        self.bayes_dir = None
        self.sql_url = None
        # We pickle the trained model. But pickle and Gio don't work well
        # together --> therefore we work directly with a path here instead of
        # an URL and with `os` instead `self.core.call_xxx("fs_xxx")`
        self.model_path = None

        self._init = False
        # we lazy-import .util because it imports scientific libs that
        # takes ages to load on Windows (about 10s if not more)
        self._util = None

        self.config = PluginConfig(core)
        self.config.register()

        self.core.call_all(
            "work_queue_create", "label_sklearn", stop_on_quit=True
        )

        self.core.call_all(
            "doc_tracker_register",
            "label_guesser",
            self._build_transaction
        )

    def _lazy_init(self):
        if self._init:
            return

        if self._util is None:
            self._util = importlib.import_module(
                "paperwork_backend.guesswork.label.sklearn.util"
            )
            self._util.SqliteNumpyArrayHandler.register()

        data_dir = self.core.call_success(
            "data_dir_handler_get_individual_data_dir"
        )

        if self.bayes_dir is None:  # may be set by tests
            self.bayes_dir = self.core.call_success(
                "fs_join", data_dir, "bayes"
            )

        self.core.call_success("fs_mkdir_p", self.bayes_dir)

        self.sql_url = self.core.call_success(
            "fs_join", self.bayes_dir, 'label_guesser.db'
        )
        self.model_path = self.core.call_success(
            "fs_unsafe", self.core.call_success(
                "fs_join", self.bayes_dir, "model.pickle"
            )
        )
        LOGGER.info("Initializing guesswork.label.sklearn database %s", self.sql_url)
        sql = self.core.call_success(
            "sqlite_open",
            self.sql_url,
            detect_types=sqlite3.PARSE_DECLTYPES,
            timeout=60
        )
        for query in CREATE_TABLES:
            sql.execute(query)
        self.core.call_success("sqlite_close", sql)

        self._init = True

    def _build_transaction(self, sync, total_expected):
        self._lazy_init()
        assert self._util is not None
        return self._util.LabelGuesserTransaction(
            self, guess_labels=not sync, total_expected=total_expected
        )

    def on_data_dir_changed(self):
        self.on_quit()

    def on_quit(self):
        self._init = False

    def reload_label_guessers(self):
        self._lazy_init()
        assert self._util is not None

        self.classifiers = None
        self.classifiers_loaded = True
        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self._util._reload_label_guessers, kwargs={"plugin": self},
        )
        self.core.call_all("work_queue_cancel_all", "label_sklearn")
        self.core.call_success(
            "work_queue_add_promise", "label_sklearn", promise
        )

    def tests_cleanup(self):
        self._init = False
