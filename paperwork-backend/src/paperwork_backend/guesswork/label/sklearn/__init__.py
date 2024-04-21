"""
Label guesser guesses label based on document text and bayes filters.
It adds the guessed labels on new documents (in other words, freshly
added documents).

It stores data in 2 ways:
- sklearn pickling of TfidVectorizer
- sqlite database
"""
import collections
import gc
import logging
import os
import pickle
import sqlite3
import threading
import time

import numpy
import scipy.sparse
import sklearn.feature_extraction.text
import sklearn.naive_bayes

import openpaperwork_core
import openpaperwork_core.promise

from .... import (_, sync)


LOGGER = logging.getLogger(__name__)
ID = "label_guesser"
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


class SqliteNumpyArrayHandler(object):
    @staticmethod
    def _to_sqlite(np_array):
        return np_array.tobytes()

    @staticmethod
    def _from_sqlite(raw):
        return numpy.frombuffer(raw)

    @classmethod
    def register(cls):
        sqlite3.register_adapter(numpy.array, cls._to_sqlite)
        sqlite3.register_converter("NUMPY_ARRAY", cls._from_sqlite)


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


class UpdatableVectorizer(object):
    """
    Vectorizer that we can update over time with new features
    (word identifiers). Store the word->features in the SQLite database.
    We only add words to the database, we never remove them, otherwise we
    wouldn't be able to read the feature vectors correctly anymore.
    """
    def __init__(self, core, db_cursor):
        self.core = core
        self.db_cursor = db_cursor

        vocabulary = self.db_cursor.execute(
            "SELECT word, feature FROM vocabulary"
        )
        vocabulary = {k.strip(): v for (k, v) in vocabulary}
        if "" in vocabulary:
            vocabulary.pop("")

        self.updatable_vocabulary = vocabulary
        self.last_feature_id = max(vocabulary.values(), default=-1)

    def partial_fit_transform(self, corpus):
        # A bit hackish: We just need the analyzer, so instantiating a full
        # TfidVectorizer() is probably overkill, but meh.
        tokenizer = sklearn.feature_extraction.text.TfidfVectorizer(
        ).build_analyzer()
        LOGGER.info(
            "Vocabulary contains %d words before fitting", self.last_feature_id
        )
        for doc_txt in corpus:
            for word in tokenizer(doc_txt):
                if word in self.updatable_vocabulary:
                    continue
                self.last_feature_id += 1
                self.db_cursor.execute(
                    "INSERT INTO vocabulary (word, feature)"
                    " SELECT ?, ?"
                    "  WHERE NOT EXISTS("
                    "   SELECT 1 FROM vocabulary WHERE word = ?"
                    "  )",
                    (word.strip(), self.last_feature_id, word)
                )
                self.updatable_vocabulary[word.strip()] = self.last_feature_id
        LOGGER.info(
            "Vocabulary contains %d words after fitting", self.last_feature_id
        )

        return self.transform(corpus)

    def transform(self, corpus):
        # IMPORTANT: we must use use_idf=False here because we want the values
        # in each feature vector to be independant from other vectors.
        try:
            vectorizer = sklearn.feature_extraction.text.TfidfVectorizer(
                use_idf=False, vocabulary=self.updatable_vocabulary
            )
            features = vectorizer.fit_transform(corpus)
            LOGGER.info("%s features extracted", features.shape)
            return features
        except ValueError as exc:
            LOGGER.warning("Failed to extract features", exc_info=exc)
            return scipy.sparse.csr_matrix((0, 0))

    def _find_unused(self):
        doc_features = self.db_cursor.execute(
            "SELECT vector FROM features"
        )
        sum_features = None
        for (doc_vector,) in doc_features:
            if doc_vector is None:
                continue
            required_padding = (
                self.last_feature_id + 1 - doc_vector.shape[0]
            )
            if required_padding > 0:
                doc_vector = numpy.hstack([
                    doc_vector,
                    numpy.zeros((required_padding,))
                ])
            if sum_features is None:
                sum_features = doc_vector
            else:
                sum_features = sum_features + doc_vector

        if sum_features is None:
            return ([], 0)

        return (
            [f for (f, v) in enumerate(sum_features) if v == 0.0],
            len(sum_features)
        )

    def _get_all_doc_ids(self):
        doc_ids = self.db_cursor.execute("SELECT doc_id FROM features")
        doc_ids = [doc_id[0] for doc_id in doc_ids]
        return doc_ids

    def gc(self):
        """
        Drop features that are unused anymore.

        IMPORTANT: After this call, the vectorizer must not be used anymore
        (this method doesn't update the internal state of the vectorizer)
        """
        # we work in the main thread so we don't have to load all the feature
        # vectors all at once in memory (we just need their sum)
        LOGGER.info("Garbage collecting unused features ...")
        (to_drop, total) = self._find_unused()
        if len(to_drop) <= 0:
            LOGGER.info("No features to garbage collect (total=%d)", total)
            return
        LOGGER.info(
            "%d/%d features will be removed from the database",
            len(to_drop), total
        )

        doc_ids = self._get_all_doc_ids()

        # first we reduce the document feature vectors
        msg = _(
            "Label guesser: Garbage-collecting unused document features ..."
        )
        self.core.call_all("on_progress", "label_vector_gc", 0.0, msg)
        for (idx, doc_id) in enumerate(doc_ids):
            self.core.call_all(
                "on_progress", "label_vector_gc", idx / len(doc_ids), msg
            )
            doc_vector = self.db_cursor.execute(
                "SELECT vector FROM features WHERE doc_id = ? LIMIT 1",
                (doc_id,)
            )
            doc_vector = list(doc_vector)
            doc_vector = doc_vector[0][0]
            if doc_vector is None:
                # may happen according to bug report #478
                doc_vector = numpy.array([])

            to_drop_for_this_doc = [f for f in to_drop if f < len(doc_vector)]
            doc_vector = numpy.delete(doc_vector, to_drop_for_this_doc)
            self.db_cursor.execute(
                "UPDATE features SET vector = ? WHERE doc_id = ?",
                (doc_vector, doc_id)
            )
        self.core.call_all("on_progress", "label_vector_gc", 1.0)

        # then we reduce the vocabulary accordingly
        msg = _("Label guesser: Garbage-collecting unused words ...")
        self.core.call_all("on_progress", "label_vocabulary_gc", 0.0, msg)
        for (idx, f) in enumerate(to_drop):
            self.core.call_all(
                "on_progress", "label_vocabulary_gc", idx / len(to_drop), msg
            )
            self.db_cursor.execute(
                "DELETE FROM vocabulary WHERE feature = ?", (f,)
            )
            self.db_cursor.execute(
                "UPDATE vocabulary SET feature = feature - 1"
                " WHERE feature >= ?", (f,)
            )
        self.core.call_all("on_progress", "label_vocabulary_gc", 1.0, )

    def copy(self):
        r = UpdatableVectorizer(self.core, self.db_cursor)
        r.updatable_vocabulary = dict(self.updatable_vocabulary)
        r.last_feature_id = self.last_feature_id
        return r


class BatchIterator(object):
    def __init__(self, config, features, targets):
        self.features = features
        self.targets = targets
        self.b = 0
        self.batch_size = config.get("batch_size")

    def __iter__(self):
        self.b = 0
        return self

    def __next__(self):
        batch_corpus = self.features[self.b:self.b + self.batch_size]
        if len(batch_corpus) <= 0:
            raise StopIteration()
        batch_corpus = scipy.sparse.vstack(batch_corpus).toarray()
        batch_targets = self.targets[self.b:self.b + self.batch_size]
        self.b += self.batch_size
        return (batch_corpus, batch_targets)


class FeatureReductor(object):
    def __init__(self, to_drop):
        self.features_to_drop = to_drop

    def reduce_features(self, features):
        return numpy.delete(features, self.features_to_drop)


class DummyFeatureReductor(object):
    def reduce_features(self, features):
        return features


class Corpus(object):
    """
    Handles doc_ids and their associate feature vectors.
    Make sure we train the document in the best order possible, so even
    if the training is interrupted (time limit), we still have some training
    for most labels.
    """
    def __init__(self, config, doc_ids, features, targets):
        self.config = config
        self.doc_ids = doc_ids
        self.features = features
        self.targets = targets

    def standardize_feature_vectors(self, vectorizer):
        for idx in range(0, len(self.features)):
            doc_vector = self.features[idx]
            required_padding = (
                vectorizer.last_feature_id + 1 - doc_vector.shape[0]
            )
            assert required_padding >= 0
            if required_padding > 0:
                doc_vector = scipy.sparse.hstack([
                    scipy.sparse.csr_matrix(doc_vector),
                    numpy.zeros((1, required_padding))
                ])
            else:
                doc_vector = scipy.sparse.csr_matrix(doc_vector)
            self.features[idx] = doc_vector

    def reduce_corpus_words(self):
        """
        We may end up with a lot of different words (about 76000 in my case).
        But most of them are actually too rare to be useful and they use
        a lot memory and CPU time.
        """
        max_words = self.config.get("max_words")

        word_freq_sums = sum(self.features).toarray()[0]
        word_count = word_freq_sums.shape[0]
        LOGGER.info("Total word count before reduction: %d", word_count)
        if word_count <= max_words:
            LOGGER.info("No reduction to do")
            return DummyFeatureReductor()

        threshold = sorted(word_freq_sums, reverse=True)[max_words]
        LOGGER.info("Word frequency threshold: %f", threshold)

        features_to_drop = []
        for (idx, freq) in enumerate(word_freq_sums):
            if freq > threshold:
                continue
            features_to_drop.append(idx)

        reductor = FeatureReductor(features_to_drop)

        for idx in range(0, len(self.features)):
            self.features[idx] = scipy.sparse.csr_matrix(
                reductor.reduce_features(
                    self.features[idx].toarray()[0]
                )
            )

        LOGGER.info(
            "Total word count after reduction: %d",
            word_count - len(reductor.features_to_drop)
        )
        return reductor

    def get_doc_count(self):
        return len(self.features)

    def get_labels(self):
        return self.targets.keys()

    def get_batches(self, label):
        return BatchIterator(self.config, self.features, self.targets[label])

    @staticmethod
    def _add_doc_ids(max_doc_backlog, doc_weights, doc_ids):
        # Assumes doc_ids are in reverse order (most recent first)
        # Also assumes most recent documents are the most useful
        assert len(doc_ids) <= max_doc_backlog
        weigth = max_doc_backlog + 1
        for doc_id in doc_ids:
            doc_weights[doc_id] += weigth
            weigth -= 1

    @staticmethod
    def load(config, cursor):
        start = time.time()

        # doc_id --> weigth
        doc_weights = collections.defaultdict(lambda: 0)

        all_labels = cursor.execute("SELECT DISTINCT label FROM labels")
        all_labels = {label[0] for label in all_labels}
        all_docs = cursor.execute(
            "SELECT doc_id FROM features ORDER BY doc_id DESC"
        )
        all_docs = [doc[0] for doc in all_docs]

        max_doc_backlog = config.get("max_doc_backlog")

        for label in all_labels:
            ds = cursor.execute(
                "SELECT doc_id FROM labels WHERE label = ?"
                " ORDER BY doc_id DESC LIMIT {}".format(max_doc_backlog),
                (label,)
            )
            Corpus._add_doc_ids(
                max_doc_backlog, doc_weights, [d[0] for d in ds]
            )

        # label --> number of doc without this label
        no_label_counts = {label: 0 for label in all_labels}
        no_label_docids = {label: [] for label in all_labels}
        for doc_id in all_docs:
            if len(no_label_counts) <= 0:
                break
            doc_labels = cursor.execute(
                "SELECT label FROM labels WHERE doc_id = ?", (doc_id,)
            )
            for label in list(no_label_counts.keys()):
                if label in doc_labels:
                    continue
                no_label_docids[label].append(doc_id)
                no_label_counts[label] += 1
                if no_label_counts[label] >= max_doc_backlog:
                    no_label_counts.pop(label)
        for doc_ids in no_label_docids.values():
            doc_ids.sort(reverse=True)
            Corpus._add_doc_ids(max_doc_backlog, doc_weights, doc_ids)

        LOGGER.info(
            "Loading features of %d documents for %d labels",
            len(doc_weights), len(all_labels)
        )

        all_features = {}
        for doc_id in doc_weights.keys():
            vectors = cursor.execute(
                "SELECT vector FROM features WHERE doc_id = ? LIMIT 1",
                (doc_id,)
            )
            for vector in vectors:
                vector = vector[0]
                if vector is None:
                    continue
                all_features[doc_id] = vector

        all_features = [
            [weight, doc_id, all_features[doc_id]]
            for (doc_id, weight) in doc_weights.items()
            if doc_id in all_features
        ]
        all_features.sort(reverse=True)
        doc_ids = [
            doc_id
            for (weight, doc_id, features) in all_features
        ]
        features = [
            features
            for (weight, doc_id, features) in all_features
        ]

        # Load labels
        targets = collections.defaultdict(list)
        for (idx, doc_id) in enumerate(doc_ids):
            doc_labels = cursor.execute(
                "SELECT label FROM labels WHERE doc_id = ?",
                (doc_id,)
            )
            doc_labels = [label[0] for label in doc_labels]
            for label in all_labels:
                present = label in doc_labels
                targets[label].append(1 if present else 0)

        corpus = Corpus(
            config=config,
            doc_ids=doc_ids,
            features=features,
            targets=targets
        )

        stop = time.time()

        LOGGER.info(
            "Took %dms to load features of %d documents",
            int((stop - start) * 1000), len(doc_ids)
        )

        return corpus


class LabelGuesserTransaction(sync.BaseTransaction):
    def __init__(self, plugin, guess_labels=False, total_expected=-1):
        super().__init__(plugin.core, total_expected)
        self.priority = plugin.PRIORITY

        self.plugin = plugin
        self.guess_labels = guess_labels

        LOGGER.info("Transaction start: Guessing labels: %s", guess_labels)

        self.cursor = None
        self.vectorizer = None
        self.lock_acquired = False

        self.nb_changes = 0
        self.need_gc = False

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()

    def _lazyinit_transaction(self):
        if self.cursor is not None:
            return

        # prevent reload of classifiers during the transaction
        assert not self.lock_acquired
        self.plugin.classifiers_cond.acquire()
        self.lock_acquired = True

        if not self.plugin.classifiers_loaded and self.guess_labels:
            # classifiers haven't been loaded at all yet. Now
            # looks like a good time for it (end of initial sync)
            self.plugin.reload_label_guessers()
        if self.plugin.classifiers is None and self.guess_labels:
            # Before starting the transaction, we wait for the classifiers
            # to be loaded, because we may need them
            # (see add_doc() -> _set_guessed_labels())
            self.plugin.classifiers_cond.wait()

        self.cursor = self.plugin.core.call_success(
            "sqlite_open",
            self.plugin.sql_url,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self.cursor.execute("BEGIN TRANSACTION")
        self.vectorizer = UpdatableVectorizer(self.core, self.cursor)

    def add_doc(self, doc_id):
        if self.guess_labels:
            # we have a higher priority than index plugins, so it is a good
            # time to update the document labels

            doc_url = self.core.call_success("doc_id_to_url", doc_id)

            has_labels = self.core.call_success(
                "doc_has_labels_by_url", doc_url
            )
            if has_labels is not None:
                LOGGER.info(
                    "Document %s already has labels. Won't guess labels",
                    doc_url
                )
                return

            self._lazyinit_transaction()
            self.plugin._set_guessed_labels(doc_url)

        else:
            self._lazyinit_transaction()

        self.notify_progress(
            ID, _("Label guesser: added document %s") % doc_id
        )
        self._upd_doc(doc_id)
        self.nb_changes += 1
        super().add_doc(doc_id)

    def upd_doc(self, doc_id):
        self._lazyinit_transaction()

        self.notify_progress(
            ID, _("Label guesser: updated document %s") % doc_id
        )
        self._upd_doc(doc_id)
        self.nb_changes += 1
        super().upd_doc(doc_id)

    def _del_doc(self, doc_id):
        self.cursor.execute("DELETE FROM labels WHERE doc_id = ?", (doc_id,))
        self.cursor.execute("DELETE FROM features WHERE doc_id = ?", (doc_id,))

    def del_doc(self, doc_id):
        self._lazyinit_transaction()

        self.notify_progress(
            ID,
            _("Label guesser: deleted document %s") % doc_id
        )
        self.nb_changes += 1
        self._del_doc(doc_id)
        LOGGER.info(
            "Document %s has been deleted."
            " Feature garbage-collecting will be run",
            doc_id
        )
        self.need_gc = True
        super().del_doc(doc_id)

    def _upd_doc(self, doc_id):
        self._del_doc(doc_id)

        doc_url = self.core.call_success("doc_id_to_url", doc_id)

        doc_labels = set()
        if doc_url is not None:
            self.core.call_all("doc_get_labels_by_url", doc_labels, doc_url)
        doc_labels = {label[0] for label in doc_labels}
        for doc_label in doc_labels:
            self.cursor.execute(
                "INSERT INTO labels (doc_id, label)"
                " VALUES (?, ?)",
                (doc_id, doc_label)
            )

        doc_txt = []
        self.core.call_all("doc_get_text_by_url", doc_txt, doc_url)
        doc_txt = "\n\n".join(doc_txt).strip()

        vector = self.vectorizer.partial_fit_transform([doc_txt])
        if vector.shape[0] <= 0 or vector.shape[1] <= 0:
            vector = numpy.array([])
        else:
            vector = vector[0].toarray()

        self.cursor.execute(
            "INSERT INTO features (doc_id, vector) VALUES (?, ?)",
            (doc_id, vector)
        )

    def cancel(self):
        try:
            self.core.call_success(
                "mainloop_schedule", self.core.call_all,
                "on_label_guesser_canceled"
            )
            if self.cursor is not None:
                self.cursor.execute("ROLLBACK")
                self.core.call_success(
                    "sqlite_close", self.cursor, optimize=False
                )
                self.cursor = None
            self.notify_done(ID)

            if not self.plugin.classifiers_loaded:
                # classifiers haven't been loaded at all yet. Now
                # looks like a good time for it (end of initial sync)
                self.plugin.reload_label_guessers()
        finally:
            if self.lock_acquired:
                self.plugin.classifiers_cond.release()
                self.lock_acquired = False

    def commit(self):
        try:
            LOGGER.info("Committing")

            if self.nb_changes > 0 and os.path.exists(self.plugin.model_path):
                os.unlink(self.plugin.model_path)

            self.core.call_success(
                "mainloop_schedule", self.core.call_all,
                "on_label_guesser_commit_start"
            )
            if self.nb_changes <= 0:
                assert self.cursor is None
                self.core.call_success(
                    "mainloop_schedule", self.core.call_all,
                    'on_label_guesser_commit_end'
                )
                LOGGER.info("Nothing to do. Training left unchanged.")
                if self.plugin.classifiers is None:
                    # classifiers haven't been loaded at all yet. Now
                    # looks like a good time for it (end of initial sync)
                    self.plugin.reload_label_guessers()
                return

            if self.need_gc:
                self.vectorizer.gc()
                self.vectorizer = None

            self.notify_progress(
                ID, _("Commiting changes for label guessing ...")
            )

            self.cursor.execute("COMMIT")
            self.core.call_success("sqlite_close", self.cursor)

            self.core.call_success(
                "mainloop_schedule", self.core.call_all,
                'on_label_guesser_commit_end'
            )
            LOGGER.info("Label guessing updated")

            self.plugin.reload_label_guessers()
        finally:
            self.notify_done(ID)
            if self.lock_acquired:
                self.plugin.classifiers_cond.release()
                self.lock_acquired = False


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    def __init__(self):
        self.bayes = None
        self.config = None

        self.sql = None

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

        SqliteNumpyArrayHandler.register()

    def get_interfaces(self):
        return [
            'sync',
        ]

    def get_deps(self):
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
                'defaults': ['paperwork_backend.doctracker'],
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

    def init(self, core):
        super().init(core)

        self.config = PluginConfig(core)
        self.config.register()

        self.core.call_all(
            "work_queue_create", "label_sklearn", stop_on_quit=True
        )

        self._init()

    def _init(self):
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
        LOGGER.info("Opening guesswork.label.sklearn database")
        self.sql = self.core.call_one(
            "sqlite_execute",
            self.core.call_success,
            "sqlite_open",
            self.sql_url,
            detect_types=sqlite3.PARSE_DECLTYPES,
            timeout=60
        )
        for query in CREATE_TABLES:
            self.sql.execute(query)

        self.core.call_all(
            "doc_tracker_register",
            "label_guesser",
            self._build_transaction
        )

    def _build_transaction(self, sync, total_expected):
        return LabelGuesserTransaction(
            self, guess_labels=not sync, total_expected=total_expected
        )

    def on_data_dir_changed(self):
        self.on_quit()
        self._init()

    def on_quit(self):
        LOGGER.info("Closing guesswork.label.sklearn database")
        self.core.call_one(
            "sqlite_execute",
            self.core.call_success,
            "sqlite_close", self.sql
        )

    def reload_label_guessers(self):
        self.classifiers = None
        self.classifiers_loaded = True
        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self._reload_label_guessers
        )
        self.core.call_all("work_queue_cancel_all", "label_sklearn")
        self.core.call_success(
            "work_queue_add_promise", "label_sklearn", promise
        )

    def _reload_label_guessers(self):
        with self.classifiers_cond:
            try:
                cursor = self.core.call_one(
                    "sqlite_open",
                    self.sql_url,
                    detect_types=sqlite3.PARSE_DECLTYPES,
                )
                try:
                    cursor.execute("BEGIN TRANSACTION")
                    self.vectorizer = UpdatableVectorizer(self.core, cursor)
                    (
                        self.word_reductor, self.classifiers
                    ) = self._load_classifiers(
                        self.model_path, cursor, self.vectorizer
                    )
                finally:
                    cursor.execute("ROLLBACK")
                    self.core.call_one("sqlite_close", cursor, optimize=False)
            finally:
                self.classifiers_cond.notify_all()

    def _load_classifiers(self, model_path, cursor, vectorizer):
        if os.path.exists(model_path):
            with open(model_path, "rb") as fd:
                LOGGER.info("Pre-trained model available. Using it")
                (reductor, classifiers) = pickle.load(fd)
            return (reductor, classifiers)

        LOGGER.info("Pre-trained model not available. Re-training one")

        # Jflesch> This is a very memory-intensive process. The Glib may try
        # to allocate memory before the GC runs and AFAIK the Glib
        # is not aware of Python GC, and so won't trigger it if required
        # (instead it will abort).
        # --> free as much memory as possible now
        # (Remember that there may be 32bits version of Paperwork out there)
        gc.collect()

        msg = _("Label guessing: Training ...")

        try:
            self.core.call_all("on_progress", "label_classifiers", 0.0, msg)

            corpus = Corpus.load(self.config, cursor)

            LOGGER.info("Training classifiers ...")
            start = time.time()

            if corpus.get_doc_count() <= 1:
                return (DummyFeatureReductor(), {})

            corpus.standardize_feature_vectors(vectorizer)
            # no need to train on all the words. Only the most used words
            reductor = corpus.reduce_corpus_words()

            # Jflesch> This is a very memory-intensive process. The Glib may
            # try to allocate memory before the GC runs and AFAIK the Glib
            # is not aware of Python GC, and so won't trigger it if required
            # (instead it will abort).
            # --> free as much memory as possible now
            gc.collect()

            classifiers = collections.defaultdict(
                sklearn.naive_bayes.GaussianNB
            )

            batch_iterators = [
                (label, corpus.get_batches(label))
                for label in corpus.get_labels()
            ]
            done = 0
            total = len(batch_iterators) * corpus.get_doc_count()

            loop_nb = 0
            timeout = False

            max_time = self.config.get("max_time")
            fit_start = time.time()
            try:
                while not timeout:
                    for (label, batch_iterator) in batch_iterators:
                        now = time.time()
                        if loop_nb > 0 and now - fit_start > max_time:
                            timeout = True
                            LOGGER.warning(
                                "Training is taking too long (%dms > %dms)."
                                " Interrupting",
                                (now - fit_start) * 1000, max_time * 1000
                            )
                            break

                        (batch_corpus, batch_targets) = next(batch_iterator)
                        self.core.call_all(
                            "on_progress", "label_classifiers", done / total,
                            _("Label guessing: Training ...")
                        )
                        classifiers[label].partial_fit(
                            batch_corpus, batch_targets,
                            classes=[0, 1]
                        )
                        done += len(batch_corpus)

                    loop_nb += 1
            except StopIteration:
                pass

            stop = time.time()
            LOGGER.info(
                "Training took %dms (Fitting: %dms) ;"
                " Training completed at %d%%",
                (stop - start) * 1000,
                (stop - fit_start) * 1000,
                done * 100 / total
            )

            # Jflesch> This is a very memory-intensive process. The Glib may
            # try to allocate memory before the GC runs and AFAIK the Glib
            # is not aware of Python GC, and so won't trigger it if required
            # (instead it will abort).
            # --> free as much memory as possible now
            gc.collect()

            with open(model_path, "wb") as fd:
                pickle.dump((reductor, classifiers), fd)
            return (reductor, classifiers)
        finally:
            self.core.call_all("on_progress", "label_classifiers", 1.0, msg)

    def _guess(self, vectorizer, reductor, classifiers, doc_url):
        LOGGER.info("Guessing labels on %s", doc_url)
        doc_txt = []
        self.core.call_all("doc_get_text_by_url", doc_txt, doc_url)
        doc_txt = "\n\n".join(doc_txt).strip()
        if doc_txt == u"":
            LOGGER.info("Can't guess. Text is empty")
            return

        vector = vectorizer.transform([doc_txt])
        vector = vector.toarray()
        if len(vector) <= 0:
            LOGGER.info(
                "Failed to vectorize text (text length=%d)",
                len(doc_txt)
            )
            return
        vector = vector[0]
        vector = reductor.reduce_features(vector)

        min_features = self.config.get("min_features")
        nb_features = 0
        for f in vector:
            if f > 0:
                nb_features += 1

        if nb_features < min_features:
            LOGGER.warning(
                "Document doesn't contain enough different words"
                " (%d ; min required is %d). Labels won't be guessed",
                nb_features, min_features
            )
            return

        LOGGER.info("Documents contains %d features", nb_features)

        for (label, classifier) in classifiers.items():
            predicted = classifier.predict([vector])[0]
            if predicted:
                yield label

    def _set_guessed_labels(self, doc_url):
        # self.classifiers_cond must locked
        assert self.classifiers is not None
        labels = self._guess(
            self.vectorizer, self.word_reductor, self.classifiers, doc_url
        )
        labels = list(labels)
        for label in labels:
            self.core.call_success("doc_add_label_by_url", doc_url, label)

    def tests_cleanup(self):
        self.core.call_success("sqlite_close", self.sql)
