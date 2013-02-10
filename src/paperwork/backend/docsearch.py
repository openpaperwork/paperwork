#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012  Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.

"""
Contains all the code relative to keyword and document list management list.
"""

import copy
import datetime
import multiprocessing
import os
import os.path
import time
import threading

import whoosh.fields
import whoosh.index
import whoosh.qparser
import whoosh.query

from paperwork.backend.img.doc import ImgDoc
from paperwork.backend.img.doc import is_img_doc
from paperwork.backend.pdf.doc import PdfDoc
from paperwork.backend.pdf.doc import is_pdf_doc
from paperwork.util import dummy_progress_cb
from paperwork.util import MIN_KEYWORD_LEN
from paperwork.util import mkdir_p
from paperwork.util import rm_rf
from paperwork.util import split_words
from paperwork.util import strip_accents


DOC_TYPE_LIST = [
    (is_pdf_doc, PdfDoc),
    (is_img_doc, ImgDoc)
]


class DummyDocSearch(object):
    docs = []
    label_list = []

    def __init__(self):
        pass

    def find_suggestions(self, sentence):
        return []

    def find_documents(self, sentence):
        return []

    def add_label(self, label):
        assert()

    def redo_ocr(self, ocrlang, progress_callback):
        assert()

    def update_label(self, old_label, new_label, cb_progress=None):
        assert()

    def destroy_label(self, label, cb_progress=None):
        assert()

    def destroy_index(self):
        assert()


class DocSearch(object):
    """
    Index a set of documents. Can provide:
        * documents that match a list of keywords
        * suggestions for user input.
        * instances of documents
    """

    INDEX_STEP_READING = "reading"
    INDEX_STEP_COMMIT = "commit"
    LABEL_STEP_UPDATING = "label updating"
    LABEL_STEP_DESTROYING = "label deletion"
    OCR_THREADS_POLLING_TIME = 0.5

    def __init__(self, rootdir, callback=dummy_progress_cb):
        """
        Index files in rootdir (see constructor)

        Arguments:
            callback --- called during the indexation (may be called *often*).
                step : DocSearch.INDEX_STEP_READING or
                    DocSearch.INDEX_STEP_SORTING
                progression : how many elements done yet
                total : number of elements to do
                document (only if step == DocSearch.INDEX_STEP_READING): file
                    being read
        """
        self.rootdir = rootdir
        base_indexdir = os.getenv("XDG_DATA_HOME",
                                  os.path.expanduser("~/.local/share"))
        self.indexdir = os.path.join(base_indexdir, "paperwork", "index")
        mkdir_p(self.indexdir)

        self.__docs_by_id = {}  # docid --> doc
        self.label_list = []

        try:
            print ("Opening index dir '%s' ..." % self.indexdir)
            self.index = whoosh.index.open_dir(self.indexdir)
        except whoosh.index.EmptyIndexError, exc:
            print ("Failed to open index '%s'" % self.indexdir)
            print ("Will try to create a new one")
            schema = whoosh.fields.Schema(
                docid=whoosh.fields.ID(stored=True, unique=True),
                content=whoosh.fields.TEXT(spelling=True),
                label=whoosh.fields.KEYWORD(stored=True, commas=True,
                                             spelling=True, scorable=True),
                last_read=whoosh.fields.DATETIME(stored=True),
            )
            self.index = whoosh.index.create_in(self.indexdir, schema)
            print ("Index '%s' created" % self.indexdir)

        self.__searcher = self.index.searcher()
        self.__qparser = whoosh.qparser.QueryParser("content",
                                                    self.index.schema)
        self.__reload_index(callback)

    def __inst_doc_from_id(self, docid):
        docpath = os.path.join(self.rootdir, docid)
        for (is_doc_type, doc_type) in DOC_TYPE_LIST:
            if is_doc_type(docpath):
                return doc_type(docpath, docid)
        print "Warning: unknown doc type: %s" % docid
        return None

    def __reload_index(self, progress_cb=dummy_progress_cb):
        query = whoosh.query.Every()
        results = self.__searcher.search(query, limit=None)

        nb_results = len(results)
        progress = 0
        labels = set()

        for result in results:
            docid = result['docid']
            doc = self.__inst_doc_from_id(docid)
            if doc is None:
                continue
            progress_cb(progress, nb_results, self.INDEX_STEP_READING, doc)
            self.__docs_by_id[docid] = doc
            for label in doc.labels:
                labels.add(label)
            progress += 1

        progress_cb(1, 1, self.INDEX_STEP_READING)

    def __delete_doc_from_index(self, index_writer, docid):
        query = whoosh.query.Term("docid", docid)
        index_writer.delete_by_query(query)

    def __update_doc_in_index(self, index_writer, doc):
        last_mod = datetime.datetime.fromtimestamp(doc.last_mod)

        query = whoosh.query.Term("docid", doc.docid)
        index_docs = self.__searcher.search(query)
        assert(len(index_docs) <= 1)

        if len(index_docs) >= 1:
            last_read = index_docs[0]['last_read']
            if last_read == last_mod:
                return False

        print ("%s has been modified. Reindexing ..." % doc.docid)

        docid = unicode(doc.docid)
        txt = u""
        for page in doc.pages:
            for line in page.text:
                txt += unicode(line) + u"\n"
        for label in doc.labels:
            txt += u" " + unicode(label.name)
        txt = txt.strip()
        txt = strip_accents(txt)
        if txt == u"":
            self.__delete_doc_from_index(index_writer, doc.docid)
            return True
        labels = u",".join([strip_accents(unicode(label.name))
                            for label in doc.labels])

        index_writer.update_document(
            docid=docid,
            content=txt,
            label=labels,
            last_read=last_mod
        )
        return True

    def index_page(self, page):
        """
        Extract all the keywords from the given page

        Arguments:
            page --- from which keywords must be extracted
        """
        index_writer = self.index.writer()
        self.__update_doc_in_index(index_writer, page.doc)
        index_writer.commit()

    def __find_documents(self, query):
        docs = []
        results = self.__searcher.search(query, limit=None)
        docids = [result['docid'] for result in results]
        docs = [self.__docs_by_id[docid] for docid in docids]
        return docs

    def __get_all_docs(self):
        query = whoosh.query.Every("docid")
        docs = self.__find_documents(query)
        docs.sort()
        docs.reverse()
        return docs

    docs = property(__get_all_docs)


    def find_documents(self, sentence):
        """
        Returns all the documents matching the given keywords

        Arguments:
            keywords --- keywords (single string)

        Returns:
            An array of document id (strings)
        """
        sentence = sentence.strip()

        if sentence == u"":
            return self.docs

        sentence = strip_accents(sentence)

        query = self.__qparser.parse(sentence)
        return self.__find_documents(query)

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
        keywords = sentence.split(" ")
        final_suggestions = []

        corrector = self.__searcher.corrector("content")
        for keyword_idx in range(0, len(keywords)):
            keyword = strip_accents(keywords[keyword_idx])
            if (len(keyword) <= MIN_KEYWORD_LEN):
                continue
            keyword_suggestions = corrector.suggest(keyword, limit=5)[:]
            for keyword_suggestion in keyword_suggestions:
                new_suggestion = keywords[:]
                new_suggestion[keyword_idx] = keyword_suggestion
                new_suggestion = u" ".join(new_suggestion)
                if len(self.find_documents(new_suggestion)) <= 0:
                    continue
                final_suggestions.append(new_suggestion)
        final_suggestions.sort()
        return final_suggestions

    def add_label(self, doc, label):
        """
        Add a label on a document.

        Arguments:
            label --- The new label (see labels.Label)
            doc --- The first document on which this label has been added
        """
        label = copy.copy(label)
        if not label in self.label_list:
            self.label_list.append(label)
            self.label_list.sort()
        doc.add_label(label)
        index_writer = self.index.writer()
        self.__update_doc_in_index(index_writer, doc)
        index_writer.commit()
        self.__searcher = self.index.searcher()

    def remove_label(self, doc, label):
        """
        Remove a label from a doc
        """
        doc.remove_label(label)
        index_writer = self.index.writer()
        self.__update_doc_in_index(index_writer, doc)
        index_writer.commit()
        self.__searcher = self.index.searcher()

    def update_label(self, old_label, new_label, callback=dummy_progress_cb):
        """
        Replace 'old_label' by 'new_label' on all the documents
        """
        self.label_list.remove(old_label)
        if new_label not in self.label_list:
            self.label_list.append(new_label)
            self.label_list.sort()
        current = 0
        total = len(self.docs)
        for doc in self.docs:
            must_reindex = (old_label in doc.labels)
            callback(current, total, self.LABEL_STEP_UPDATING, doc)
            doc.update_label(old_label, new_label)
            if must_reindex:
                self.__update_doc_in_index(index_writer, doc)
            current += 1
        self.__searcher = self.index.searcher()

    def destroy_label(self, label, callback=dummy_progress_cb):
        """
        Remove the label 'label' from all the documents
        """
        self.label_list.remove(label)
        current = 0
        docs = self.docs
        total = len(docs)
        for doc in docs:
            must_reindex = (label in doc.labels)
            callback(current, total, self.LABEL_STEP_DESTROYING, doc)
            doc.remove_label(label)
            if must_reindex:
                self.__update_doc_in_index(index_writer, doc)
            current += 1
        self.__searcher = self.index.searcher()

    def redo_ocr(self, ocrlang, progress_callback=dummy_progress_cb):
        """
        Rerun the OCR on *all* the documents. Can be a *really* long process,
        which is why progress_callback is a mandatory argument.

        Arguments:
            progress_callback --- See util.dummy_progress_cb for a
                prototype. The only step returned is "INDEX_STEP_READING"
            ocrlang --- Language to specify to the OCR tool (see
                config.PaperworkConfig.ocrlang)
        """
        print "Redoing OCR of all documents ..."

        dlist = os.listdir(self.rootdir)
        threads = []
        remaining = dlist[:]

        max_threads = multiprocessing.cpu_count()

        while (len(remaining) > 0 or len(threads) > 0):
            for thread in threads:
                if not thread.is_alive():
                    threads.remove(thread)
            while (len(threads) < max_threads and len(remaining) > 0):
                docid = remaining.pop()
                docpath = os.path.join(self.rootdir, docid)
                doc = self.get_doc(docpath, docid)
                if doc == None:
                    continue
                thread = threading.Thread(target=doc.redo_ocr,
                                          args=[ocrlang], name=docid)
                thread.start()
                threads.append(thread)
                progress_callback(len(dlist) - len(remaining),
                                  len(dlist), self.INDEX_STEP_READING,
                                  doc)
            time.sleep(self.OCR_THREADS_POLLING_TIME)
        print "OCR of all documents done"

    def destroy_index(self):
        """
        Destroy the index. Don't use this DocSearch object anymore after this
        call. Next instantiation of a DocSearch will rebuild the whole index
        """
        print "Destroying the index ..."
        rm_rf(self.indexdir)
        print "Done"
