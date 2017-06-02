#!/usr/bin/env python3

import collections
import copy
import datetime
import gc
import logging
import multiprocessing
import threading

import whoosh.fields
import whoosh.index
import whoosh.qparser
import whoosh.query
import whoosh.sorting

from .common.page import BasicPage
from .fs import GioFileSystem
from .labels import LabelGuesser
from .img.doc import ImgDoc
from .img.doc import is_img_doc
from .pdf.doc import PdfDoc
from .pdf.doc import is_pdf_doc
from .util import hide_file
from .util import MIN_KEYWORD_LEN
from .util import mkdir_p
from .util import rm_rf
from .util import strip_accents


logger = logging.getLogger(__name__)


COMMAND = collections.namedtuple(
    "COMMAND", ["func", "args", "kwargs"]
)
RESULT = collections.namedtuple(
    "RESULT", ["exc", "ret"]
)


DOC_TYPE_LIST = [
    (is_pdf_doc, PdfDoc.doctype, PdfDoc),
    (is_img_doc, ImgDoc.doctype, ImgDoc)
]


class PaperworkIndex(object):
    WHOOSH_SCHEMA = whoosh.fields.Schema(
        # static up to date schema
        docid=whoosh.fields.ID(stored=True, unique=True),
        doctype=whoosh.fields.ID(stored=True, unique=False),
        docfilehash=whoosh.fields.ID(stored=True),
        content=whoosh.fields.TEXT(spelling=True),
        label=whoosh.fields.KEYWORD(stored=True, commas=True,
                                    scorable=True),
        date=whoosh.fields.DATETIME(stored=True),
        last_read=whoosh.fields.DATETIME(stored=True),
    )

    def __init__(self):
        self.fs = GioFileSystem()

        self.indexdir = None
        self.index = None
        self.label_guesser_dir = None
        self._docs_by_id = {}  # docid --> doc
        self.labels = {}  # label name --> label
        self.__searcher = None
        self.label_guesser = None
        self.search_param_list = {}
        self.label_guesser = None
        self.rootdir = None
        self.opened = False
        self.running = True

        self.reload_index_data = {}
        self.examine_rootdir_data = {}
        self.index_update_data = {}
        self.index_writer = None
        self.label_guesser_updater = None
        self.update_label_data = {}
        self.destroy_label_data = {}

        (self.pipe_client, self.pipe_server) = multiprocessing.Pipe()
        self.process = multiprocessing.Process(target=self.run)
        self.process.daemon = True
        self.process.start()

    def run(self):
        while self.running:
            command = self.pipe_server.recv()
            try:
                func = getattr(self, command.func)
                ret = func(*command.args, **command.kwargs)
                self.pipe_server.send(RESULT(exc=None, ret=ret))
            except BaseException as exc:
                logger.exception("Exception while calling '%s'", command.func)
                self.pipe_server.send(RESULT(exc=exc, ret=None))

    def open(self, localdir, base_data_dir, index_path, label_guesser_path,
             rootdir, language=None):
        self.rootdir = self.fs.safe(rootdir)
        self.indexdir = index_path
        self.label_guesser_dir = label_guesser_path

        need_index_rewrite = True
        while need_index_rewrite:
            try:
                logger.info("Opening index dir '%s' ..." % self.indexdir)
                self.index = whoosh.index.open_dir(self.indexdir)
                # check that the schema is up-to-date
                # We use the string representation of the schemas, because
                # previous versions of whoosh don't always implement __eq__
                if str(self.index.schema) != str(self.WHOOSH_SCHEMA):
                    raise Exception("Index version mismatch")
                self.__searcher = self.index.searcher()
                need_index_rewrite = False
            except Exception as exc:
                logger.warning(
                    "Failed to open index '%s'."
                    " Will rebuild index from scratch", self.indexdir,
                    exc_info=exc
                )

            if need_index_rewrite:
                logger.info("Creating a new index")
                self.destroy_index()
                mkdir_p(self.indexdir)
                mkdir_p(self.label_guesser_dir)
                new_index = whoosh.index.create_in(
                    self.indexdir,
                    self.WHOOSH_SCHEMA
                )
                new_index.close()
                logger.info("Index '%s' created" % self.indexdir)
                if localdir in base_data_dir:
                    # windows support
                    hide_file(localdir)

        class CustomFuzzy(whoosh.qparser.query.FuzzyTerm):
            def __init__(self, fieldname, text, boost=1.0, maxdist=1,
                         prefixlength=0, constantscore=True):
                whoosh.qparser.query.FuzzyTerm.__init__(
                    self, fieldname, text, boost, maxdist,
                    prefixlength, constantscore=True
                )

        facets = [
            whoosh.sorting.ScoreFacet(),
            whoosh.sorting.FieldFacet("date", reverse=True)
        ]

        self.search_param_list = {
            'fuzzy': [
                {
                    "query_parser": whoosh.qparser.MultifieldParser(
                        ["label", "content"], schema=self.index.schema,
                        termclass=CustomFuzzy),
                    "sortedby": facets
                },
                {
                    "query_parser": whoosh.qparser.MultifieldParser(
                        ["label", "content"], schema=self.index.schema,
                        termclass=whoosh.qparser.query.Prefix),
                    "sortedby": facets
                },
            ],
            'strict': [
                {
                    "query_parser": whoosh.qparser.MultifieldParser(
                        ["label", "content"], schema=self.index.schema,
                        termclass=whoosh.query.Term),
                    "sortedby": facets
                },
            ],
        }

        self.label_guesser = LabelGuesser(
            self.label_guesser_dir, len(self._docs_by_id.keys())
        )
        self.label_guesser.set_language(language)

        self.fs.mkdir_p(self.rootdir)
        self.opened = True

    def set_language(self, language):
        self.label_guesser.set_language(language)

    def start_reload_index(self):
        docs_by_id = self._docs_by_id
        self._docs_by_id = {}
        del docs_by_id

        results = self.__searcher.search(
            whoosh.query.Every(), limit=None
        )
        self.reload_index_data['results'] = results
        self.reload_index_data['results_iter'] = iter(results)
        self.reload_index_data['labels'] = set()
        self.reload_index_data['done'] = 0
        return len(results)

    def __inst_doc(self, docid, doc_type_name=None):
        """
        Instantiate a document based on its document id.
        The information are taken from the whoosh index.
        """
        doc = None
        docpath = self.fs.join(self.rootdir, docid)
        if not self.fs.exists(docpath):
            return None
        if doc_type_name is not None:
            # if we already know the doc type name
            for (is_doc_type, doc_type_name_b, doc_type) in DOC_TYPE_LIST:
                if (doc_type_name_b == doc_type_name):
                    doc = doc_type(self.fs, docpath, docid)
            if not doc:
                logger.warning(
                    ("Warning: unknown doc type found in the index: %s") %
                    doc_type_name
                )
        # otherwise we guess the doc type
        if not doc:
            for (is_doc_type, doc_type_name, doc_type) in DOC_TYPE_LIST:
                if is_doc_type(self.fs, docpath):
                    doc = doc_type(self.fs, docpath, docid)
                    break
        if not doc:
            logger.warning("Warning: unknown doc type for doc '%s'" % docid)

        return doc

    def continue_reload_index(self):
        result = None
        try:
            result = next(self.reload_index_data['results_iter'])
        except StopIteration:
            return False

        doc = self.__inst_doc(result['docid'], result['doctype'])
        if doc is None:
            return

        self._docs_by_id[result['docid']] = doc
        for label in doc.labels:
            self.reload_index_data['labels'].add(label)

        return True

    def end_reload_index(self):
        self.label_guesser = LabelGuesser(
            self.label_guesser_dir,
            len(self._docs_by_id.keys())
        )
        for label in self.reload_index_data['labels']:
            self.label_guesser.load(label.name)

        self.labels = {
            label.name: label
            for label in self.reload_index_data['labels']
        }
        self.reload_index_data = {}

    def start_examine_rootdir(self):
        results = self.__searcher.search(whoosh.query.Every(), limit=None)
        old_doc_list = set([result['docid'] for result in results])
        old_doc_infos = {}
        for result in results:
            old_doc_infos[result['docid']] = (
                result['doctype'], result['last_read']
            )
        docdirs = [x for x in self.fs.listdir(self.rootdir)]
        self.examine_rootdir_data['old_doc_list'] = old_doc_list
        self.examine_rootdir_data['old_doc_infos'] = old_doc_infos
        self.examine_rootdir_data['docdirs'] = docdirs
        self.examine_rootdir_data['docdirs_iter'] = iter(docdirs)
        return len(docdirs)

    def get_doc_from_docid(self, docid, doc_type_name=None, inst=True):
        """
        Try to find a document based on its document id. if inst=True, if it
        hasn't been instantiated yet, it will be.
        """
        assert(docid is not None)
        if docid in self._docs_by_id:
            return self._docs_by_id[docid]
        if not inst:
            return None
        doc = self.__inst_doc(docid, doc_type_name)
        if doc is None:
            return None
        self._docs_by_id[docid] = doc
        return doc

    def continue_examine_rootdir(self):
        docpath = None
        try:
            docpath = next(self.examine_rootdir_data['docdirs_iter'])
        except StopIteration:
            self.examine_rootdir_data['old_doc_list_iter'] = iter(
                self.examine_rootdir_data['old_doc_list']
            )
            return ('end', None)

        docdir = self.fs.basename(docpath)
        old_infos = self.examine_rootdir_data['old_doc_infos'].get(docdir)
        doctype = None
        if old_infos is not None:
            doctype = old_infos[0]
        doc = self.get_doc_from_docid(docdir, doctype, inst=True)
        if doc is None:
            return ('continue', None)
        old_doc_list = self.examine_rootdir_data['old_doc_list']
        if docdir in old_doc_list:
            old_doc_list.remove(docdir)
            assert(old_infos is not None)
            last_mod = datetime.datetime.fromtimestamp(doc.last_mod)
            if old_infos[1] != last_mod:
                return ('modified', doc.clone())
            else:
                return ('unchanged', doc.clone())
        else:
            return ('new', doc.clone())

    def continue_examine_rootdir2(self):
        old_doc = None
        try:
            old_doc = next(self.examine_rootdir_data['old_doc_list_iter'])
        except StopIteration:
            return ('end', None)

        docpath = self.fs.join(self.rootdir, old_doc)
        return ('deleted', ImgDoc(self.fs, docpath, old_doc))

    def end_examine_rootdir(self):
        self.examine_rootdir_data = {}

    def _update_doc_in_index(self, index_writer, doc):
        """
        Add/Update a document in the index
        """
        all_labels = set(self.label_list)
        doc_labels = set(doc.labels)
        new_labels = doc_labels.difference(all_labels)

        # can happen when we recreate the index from scratch
        for label in new_labels:
            self.create_label(label)

        last_mod = datetime.datetime.fromtimestamp(doc.last_mod)
        docid = str(doc.docid)

        dochash = doc.get_docfilehash()
        dochash = (u"%X" % dochash)

        doc_txt = doc.get_index_text()
        assert(isinstance(doc_txt, str))
        labels_txt = doc.get_index_labels()
        assert(isinstance(labels_txt, str))

        # append labels to doc txt, because we usually search on doc_txt
        doc_txt += " " + labels_txt

        query = whoosh.query.Term("docid", docid)
        index_writer.delete_by_query(query)

        index_writer.update_document(
            docid=docid,
            doctype=doc.doctype,
            docfilehash=dochash,
            content=strip_accents(doc_txt),
            label=strip_accents(labels_txt),
            date=doc.date,
            last_read=last_mod
        )
        return True

    @staticmethod
    def _delete_doc_from_index(index_writer, docid):
        """
        Remove a document from the index
        """
        query = whoosh.query.Term("docid", docid)
        index_writer.delete_by_query(query)

    def add_doc(self, doc, index_update=True, label_guesser_update=True):
        """
        Add a document to the index
        """
        if not self.index_writer and index_update:
            self.index_writer = self.index.writer()
        if not self.label_guesser_updater and label_guesser_update:
            self.label_guesser_updater = self.label_guesser.get_updater()
        logger.info("Indexing new doc: %s" % doc)
        if index_update:
            self._update_doc_in_index(self.index_writer, doc)
        if label_guesser_update:
            self.label_guesser_updater.add_doc(doc)
        if doc.docid not in self._docs_by_id:
            self._docs_by_id[doc.docid] = doc

    def upd_doc(self, doc, index_update=True, label_guesser_update=True):
        """
        Update a document in the index
        """
        if not self.index_writer and index_update:
            self.index_writer = self.index.writer()
        if not self.label_guesser_updater and label_guesser_update:
            self.label_guesser_updater = self.label_guesser.get_updater()
        logger.info("Updating modified doc: %s" % doc)
        if index_update:
            self._update_doc_in_index(self.index_writer, doc)
        if label_guesser_update:
            self.label_guesser_updater.upd_doc(doc)

    def del_doc(self, doc):
        """
        Delete a document
        """
        if not self.index_writer:
            self.index_writer = self.index.writer()
        if not self.label_guesser_updater:
            self.label_guesser_updater = self.label_guesser.get_updater()
        logger.info("Removing doc from the index: %s" % doc)
        if doc.docid in self._docs_by_id:
            self._docs_by_id.pop(doc.docid)
        if isinstance(doc, str):
            # annoying case : we can't know which labels were on it
            # so we can't roll back the label guesser training ...
            self._delete_doc_from_index(self.index_writer, doc)
            return
        self._delete_doc_from_index(self.index_writer, doc.docid)
        self.label_guesser_updater.del_doc(doc)

    def commit(self, index_update=True, label_guesser_update=True):
        """
        Apply the changes to the index
        """
        logger.info("Index: Commiting changes")
        if self.index_writer:
            if index_update:
                self.index_writer.commit()
            else:
                self.index_writer.cancel()
            del self.index_writer
        self.index_writer = None

        self.index.refresh()

        if self.label_guesser:
            if label_guesser_update and self.label_guesser_updater is not None:
                self.label_guesser_updater.commit()
            if index_update:
                self.reload_searcher()

    def cancel(self):
        """
        Forget about the changes
        """
        logger.info("Index: Index update cancelled")
        if self.index_writer:
            self.index_writer.cancel()
            del self.index_writer
        self.index_writer = None
        if self.label_guesser_updater:
            self.label_guesser_updater.cancel()
        self.label_guesser_updater = None

    def reload_searcher(self):
        searcher = self.__searcher
        self.__searcher = self.index.searcher()
        del(searcher)

    def guess_labels(self, doc):
        """
        return a prediction of label names
        """
        if doc.nb_pages <= 0:
            return set()
        self.label_guesser.total_nb_documents = len(self._docs_by_id.keys())
        label_names = self.label_guesser.guess(doc)
        labels = set()
        for label_name in label_names:
            label = self.labels[label_name]
            labels.add(label)
        return labels

    def get_all_docs(self):
        return [x for x in self._docs_by_id.values()]

    def get_nb_docs(self):
        return len(self._docs_by_id)

    def get(self, obj_id):
        """
        Get a document or a page using its ID
        Won't instantiate them if they are not yet available
        """
        if BasicPage.PAGE_ID_SEPARATOR in obj_id:
            (docid, page_nb) = obj_id.split(BasicPage.PAGE_ID_SEPARATOR)
            page_nb = int(page_nb)
            return self._docs_by_id[docid].pages[page_nb]
        return self._docs_by_id[obj_id]

    def find_documents(self, sentence, limit=None, must_sort=True,
                       search_type='fuzzy'):
        """
        Returns all the documents matching the given keywords

        Arguments:
            sentence --- a sentenced query
        Returns:
            An array of document (doc objects)
        """
        sentence = sentence.strip()
        sentence = strip_accents(sentence)

        if sentence == u"":
            return self.get_all_docs()

        result_list_list = []
        total_results = 0

        for query_parser in self.search_param_list[search_type]:
            query = query_parser["query_parser"].parse(sentence)

            sortedby = None
            if must_sort and "sortedby" in query_parser:
                sortedby = query_parser['sortedby']
            if sortedby:
                results = self.__searcher.search(
                    query, limit=limit, sortedby=sortedby
                )
            else:
                results = self.__searcher.search(
                    query, limit=limit
                )
            results = [
                (result['docid'], result['doctype'])
                for result in results
            ]

            result_list_list.append(results)
            total_results += len(results)

            if not must_sort and total_results >= limit:
                break

        # merging results
        docs = set()
        for result_intermediate in result_list_list:
            for result in result_intermediate:
                doc = self._docs_by_id.get(result[0])
                if doc is None:
                    continue
                docs.add(doc)

        docs = [d for d in docs]

        if not must_sort and limit is not None:
            docs = docs[:limit]

        return docs

    def find_suggestions(self, sentence):
        """
        Search all possible suggestions. Suggestions returned always have at
        least one document matching.

        Arguments:
            sentence --- keywords (single strings) for which we want
                suggestions
        Return:
            An array of sets of keywords. Each set of keywords (-> one string)
            is a suggestion.
        """
        if not isinstance(sentence, str):
            sentence = str(sentence)

        keywords = sentence.split(" ")

        query_parser = self.search_param_list['strict'][0]['query_parser']

        base_search = u" ".join(keywords).strip()
        final_suggestions = []
        corrector = self.__searcher.corrector("content")
        label_corrector = self.__searcher.corrector("label")
        for (keyword_idx, keyword) in enumerate(keywords):
            if (len(keyword) <= MIN_KEYWORD_LEN):
                continue
            keyword_suggestions = label_corrector.suggest(
                keyword, limit=2
            )[:]
            keyword_suggestions += corrector.suggest(keyword, limit=5)[:]
            for keyword_suggestion in keyword_suggestions:
                new_suggestion = keywords[:]
                new_suggestion[keyword_idx] = keyword_suggestion
                new_suggestion = u" ".join(new_suggestion).strip()

                if new_suggestion == base_search:
                    continue

                # make sure it would return results
                query = query_parser.parse(new_suggestion)
                results = self.__searcher.search(query, limit=1)
                if len(results) <= 0:
                    continue
                final_suggestions.append(new_suggestion)
        final_suggestions.sort()
        return final_suggestions

    def create_label(self, label, doc=None):
        """
        Create a new label

        Arguments:
            doc --- first document on which the label must be added (required
                    for now)
        """
        label = copy.copy(label)
        assert(label not in self.labels.values())
        self.labels[label.name] = label
        self.label_guesser.load(label.name)
        # TODO(Jflesch): Should train with previous documents
        if doc:
            doc.add_label(label)
            self.upd_doc(doc)
            self.commit()

    def add_label(self, doc, label, update_index=True):
        """
        Add a label on a document.

        Arguments:
            label --- The new label (see labels.Label)
            doc --- The first document on which this label has been added
        """
        label = copy.copy(label)
        assert(label in self.labels.values())
        doc.add_label(label)
        if update_index:
            self.upd_doc(doc)
            self.commit()

    def remove_label(self, doc, label, update_index=True):
        """
        Remove a label from a doc. Takes care of updating the index
        """
        doc.remove_label(label)
        if update_index:
            self.upd_doc(doc)
            self.commit()

    def start_update_label(self, old_label, new_label):
        assert(old_label)
        assert(new_label)
        self.labels.pop(old_label.name)
        if new_label not in self.labels.values():
            self.labels[new_label.name] = new_label
        self.update_label_data['docs'] = iter(self.get_all_docs())
        self.update_label_data['old_label'] = old_label
        self.update_label_data['new_label'] = new_label

    def continue_update_label(self):
        doc = None
        try:
            doc = next(self.update_label_data['docs'])
        except StopIteration:
            return ('end', None)

        old_label = self.update_label_data['old_label']
        new_label = self.update_label_data['new_label']
        must_reindex = old_label in doc.labels
        doc.update_label(old_label, new_label)
        if must_reindex:
            self.upd_doc(doc, label_guesser_update=False)
        return ('updated', doc.clone())

    def end_update_label(self):
        self.commit()

        old_label = self.update_label_data['old_label']
        new_label = self.update_label_data['new_label']
        if old_label.name != new_label.name:
            self.label_guesser.rename(old_label.name, new_label.name)
        self.update_label_data = {}

    def start_destroy_label(self, label):
        assert(label)
        self.labels.pop(label.name)
        self.destroy_label_data['docs'] = iter(self.get_all_docs())
        self.destroy_label_data['label'] = label

    def continue_destroy_label(self):
        doc = None
        try:
            doc = next(self.destroy_label_data['docs'])
        except StopIteration:
            return ('end', None)
        label = self.destroy_label_data['label']
        must_reindex = (label in doc.labels)
        doc.remove_label(label)
        if must_reindex:
            self.upd_doc(doc, label_guesser_update=False)

    def end_destroy_label(self):
        label = self.destroy_label_data['label']
        self.commit()
        self.label_guesser.forget(label.name)
        self.destroy_label_data = {}

    def close(self):
        self.opened = False
        if self.__searcher:
            self.__searcher.close()
            del self.__searcher
        self.__searcher = None
        if self.index:
            self.index.close()
            del self.index
        self.index = None
        if self.label_guesser:
            del self.label_guesser
        self.label_guesser = None

    def stop(self):
        self.close()
        self.running = False

    def destroy_index(self):
        """
        Destroy the index. Don't use this Index object anymore after this
        call. Index will have to be rebuilt from scratch
        """
        self.close()
        logger.info("Destroying the index ...")
        rm_rf(self.indexdir)
        rm_rf(self.label_guesser_dir)
        logger.info("Done")

    def is_hash_in_index(self, filehash):
        """
        Check if there is a document using this file hash
        """
        filehash = (u"%X" % filehash)
        results = self.__searcher.search(
            whoosh.query.Term('docfilehash', filehash))
        return bool(results)

    def get_label_list(self):
        labels = [label for label in self.labels.values()]
        labels.sort()
        return labels

    def set_label_list(self, label_list):
        for label in label_list:
            self.label_guesser.load(label.name)
        labels = {label.name: label for label in label_list}
        self.labels = labels

    label_list = property(get_label_list, set_label_list)

    def gc(self):
        gc.collect()


class MethodProxy(object):
    def __init__(self, client, method_name):
        self.client = client
        self.method_name = method_name

    def __call__(self, *args, **kwargs):
        return self.client.remote_call(self.method_name, *args, **kwargs)


class PaperworkIndexClient(object):
    def __init__(self):
        server = PaperworkIndex()
        self.pipe = server.pipe_client
        self.lock = threading.Lock()

    def remote_call(self, func_name, *args, **kwargs):
        with self.lock:
            cmd = COMMAND(func=func_name, args=args, kwargs=kwargs)
            self.pipe.send(cmd)
            ret = self.pipe.recv()
            if ret.exc:
                raise ret.exc
            return ret.ret

    def __getattr__(self, name):
        return MethodProxy(self, name)
