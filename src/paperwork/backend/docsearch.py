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

import multiprocessing
import os
import os.path
import time
import threading

from paperwork.backend.img.doc import ImgDoc
from paperwork.backend.img.doc import is_img_doc
from paperwork.backend.pdf.doc import PdfDoc
from paperwork.backend.pdf.doc import is_pdf_doc
from paperwork.util import dummy_progress_cb
from paperwork.util import MIN_KEYWORD_LEN
from paperwork.util import split_words


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


class DocSearch(object):
    """
    Index a set of documents. Can provide:
        * documents that match a list of keywords
        * suggestions for user input.
        * instances of documents
    """

    INDEX_STEP_READING = "reading"
    INDEX_STEP_SORTING = "sorting"
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

        # we don't use __reset_data() here. Otherwise pylint won't be happy.
        self.__keywords = []            # array of strings (sorted)
        self.docs = []                # array of doc (sorted)
        self.__keywords_to_docs = {}    # keyword (string) -> doc paths
        self.label_list = []

        self.__index(callback)

    @staticmethod
    def get_doc(docpath, docid):
        files = os.listdir(docpath)
        for (is_doc_type, doc_type) in DOC_TYPE_LIST:
            if is_doc_type(files):
                return doc_type(docpath, docid)
        print ("Warning: Unidentified doctype: %s / %s" % (docpath, docid))
        return None

    def __reset_data(self):
        """
        Purge the lists of documents and keywords
        """
        self.__keywords = []
        self.docs = []
        self.__keywords_to_docs = {}
        self.label_list = []

    def __index_keyword(self, doc, keyword):
        """
        Add the specified keyword to the index.

        Arguments:
            doc --- the document from which comes the keyword
            keyword --- the keyword
        """
        if keyword in self.__keywords_to_docs:
            docs = self.__keywords_to_docs[keyword]
            if not doc in docs:
                docs.append(doc)
        else:
            self.__keywords_to_docs[keyword] = [doc]

    def __index_doc(self, doc):
        """
        Add the keywords from the document to self.__keywords_to_docs
        """
        self.docs.append(doc)
        for keyword in doc.keywords:
            self.__index_keyword(doc, keyword)

    def __index_dir(self, dirpath, callback=dummy_progress_cb):
        """
        Look in the given directory for documents to index.
        May also be called on the directory of a document itself.

        Arguments:
            dirpath --- directory to explore
            callback -- progression indicator callback (see
                util.dummy_progress_cb)
        """
        try:
            dlist = os.listdir(dirpath)
        except OSError, exc:
            print "Unable to read dir '%s': %s" % (dirpath, str(exc))
            return
        dlist.sort()

        progression = 0
        total = len(dlist)

        for dpath in dlist:
            if dpath[:1] == "." or dpath[-1:] == "~":
                progression = progression + 1
                continue
            elif os.path.isdir(os.path.join(dirpath, dpath)):
                docpath = os.path.join(dirpath, dpath)
                doc = self.get_doc(docpath, dpath)
                if doc == None:
                    continue
                callback(progression, total, self.INDEX_STEP_READING, doc)
                self.__index_doc(doc)
                for label in doc.labels:
                    self.add_label(label, doc)
            progression = progression + 1

    @staticmethod
    def __docpath_to_id(docpath):
        """
        Generate a document id baed on a document path.
        """
        try:
            return os.path.split(docpath)[1]
        except IndexError:
            print "Warning: Invalid document path: %s" % (docpath)
            return docpath

    def __extract_keywords(self, callback=dummy_progress_cb):
        """
        Extract and index all the keywords from all the documents in
        self.rootdir.
        """
        callback(1, 3, self.INDEX_STEP_SORTING)
        self.__keywords = self.__keywords_to_docs.keys()
        for label in self.label_list:
            if not label.name in self.__keywords:
                self.__keywords.append(label.name)
        callback(2, 3, self.INDEX_STEP_SORTING)
        self.__keywords.sort()
        self.docs.sort()

    def __index(self, callback=dummy_progress_cb):
        """
        Index all the documents in self.rootdir.

        Arguments:
            callback --- progression indicator callback (see
                util.dummy_progress_cb)
        """
        self.__reset_data()
        self.__index_dir(self.rootdir, callback=callback)
        self.__extract_keywords(callback)

    def index_page(self, page):
        """
        Extract all the keywords from the given page

        Arguments:
            page --- from which keywords must be extracted
        """
        if not page.doc in self.docs:
            self.docs.append(page.doc)
            self.docs.sort()
        for keyword in page.keywords:
            self.__index_keyword(page.doc, keyword)
        # remake these two:
        self.__extract_keywords(dummy_progress_cb)

    def __get_keyword_suggestions(self, keyword):
        """
        Return all the suggestions for a single keyword.

        Arguments:
            keyword --- keyword (string) for which we are looking for
                suggestions

        Returns:
            An array of suggestions (strings)
        """
        neg = (keyword[:1] == "!")
        if neg:
            keyword = keyword[1:]

        lkeyword = len(keyword)
        lkeywords = len(self.__keywords)

        if lkeyword < MIN_KEYWORD_LEN:
            return []

        # the array is sorted. So we use dichotomy to
        # figure the position of the first element matching the keyword
        # and the position of the last one

        # first element
        njump = (lkeywords / 4) or 1
        idx_min = lkeywords / 2
        idx_min_found = False

        while not idx_min_found:
            if idx_min <= 0 or idx_min > lkeywords - 1:
                idx_min_found = True
            elif (self.__keywords[idx_min - 1][:lkeyword] < keyword
                  and self.__keywords[idx_min][:lkeyword] > keyword):
                print "No suggestion found for '%s'" % keyword
                return []
            elif (self.__keywords[idx_min - 1][:lkeyword] != keyword
                  and self.__keywords[idx_min][:lkeyword] == keyword):
                idx_min_found = True
            elif self.__keywords[idx_min][:lkeyword] >= keyword:
                idx_min = idx_min - njump
            else:
                idx_min = idx_min + njump
            njump = (njump / 2) or 1

        if idx_min > lkeywords - 1:
            print "No suggestion found for '%s'" % keyword
            return []

        # last element
        njump = ((lkeywords - idx_min) / 4) or 1
        idx_max = ((lkeywords - idx_min) / 2) + idx_min
        idx_max_found = False

        while not idx_max_found:
            if idx_max <= 0 or idx_max >= lkeywords - 1:
                idx_max_found = True
            elif (self.__keywords[idx_max + 1][:lkeyword] != keyword
                  and self.__keywords[idx_max][:lkeyword] == keyword):
                idx_max_found = True
            elif self.__keywords[idx_max][:lkeyword] <= keyword:
                idx_max = idx_max + njump
            else:
                idx_max = idx_max - njump
            njump = (njump / 2) or 1

        results = self.__keywords[idx_min:(idx_max + 1)]

        if neg:
            results = [("!%s" % (result)) for result in results]

        print "Got %d suggestions for [%s]" % (len(results), keyword)

        return results

    def __find_suggestions(self, keywords):
        """
        see DocSearch.find_suggestions().
        """
        if len(keywords) <= 0:
            return []

        # search suggestion for the first keywords
        first_keyword_suggestions = self.__get_keyword_suggestions(keywords[0])
        if len(keywords) <= 1:
            return first_keyword_suggestions

        results = []

        # .. and for all the remaining keywords
        # XXX(Jflesch): recursivity
        other_keywords_suggestions = self.__find_suggestions(keywords[1:])

        for first_keyword_suggestion in first_keyword_suggestions:
            for suggestion in other_keywords_suggestions:
                suggestion = first_keyword_suggestion + " " + suggestion
                # immediatly look if it has matching documents
                if len(self.find_documents(suggestion)) <= 0:
                    continue
                results.append(suggestion)

        return results

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
        keywords = split_words(sentence)
        results = self.__find_suggestions([x for x in keywords])
        try:
            results.remove(sentence)    # remove strict match if it is here
        except ValueError:
            pass
        results.sort()
        return results

    def __find_documents(self, keyword):
        """
        Returns all the documents matching the given keywords

        Arguments:
            keyword --- one keyword (string)

        Returns:
            An array of docs
        """
        try:
            return self.__keywords_to_docs[keyword][:]
        except KeyError:
            return []

    def find_documents(self, sentence):
        """
        Returns all the documents matching the given keywords

        Arguments:
            keywords --- keywords (single string)

        Returns:
            An array of document id (strings)
        """

        if sentence.strip() == "":
            return self.docs[:]

        positive_keywords = []
        negative_keywords = []

        print ("Looking for documents containing %s"
               % (sentence.encode('ascii', 'replace')))

        for keyword in split_words(sentence):
            if keyword[:1] != "!":
                positive_keywords.append(keyword)
            else:
                negative_keywords.append(keyword[1:])

        if (len(positive_keywords) == 0 and len(negative_keywords) == 0):
            return []

        documents = None

        if len(positive_keywords) <= 0:
            positive_keywords = ["*"]

        for keyword in positive_keywords:
            docs = self.__find_documents(keyword)
            if documents == None:
                documents = docs
            else:
                # intersection of both arrays
                documents = [val for val in documents if val in docs]

        if documents == None:
            return []

        print "Found %d documents" % (len(documents))

        for keyword in negative_keywords:
            docs = self.__find_documents(keyword)
            print "Found %d documents to remove" % (len(documents))
            for doc in docs:
                try:
                    documents.remove(doc)
                except ValueError:
                    pass

        documents.sort()
        return documents

    def add_label(self, label, doc):
        """
        Add a new label to the list of known labels.

        Arguments:
            label --- The new label (see labels.Label)
            doc --- The first document on which this label has been added
        """
        label_words = split_words(label.name)
        for word in label_words:
            self.__index_keyword(doc, word)
            if not word in self.__keywords:
                self.__keywords.append(word)
                self.__keywords.sort()
        if not label in self.label_list:
            self.label_list.append(label)
            self.label_list.sort()

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
            callback(current, total, self.LABEL_STEP_UPDATING, doc)
            doc.update_label(old_label, new_label)
            current += 1

    def destroy_label(self, label, callback=dummy_progress_cb):
        """
        Remove the label 'label' from all the documents
        """
        self.label_list.remove(label)
        current = 0
        total = len(self.docs)
        for doc in self.docs:
            callback(current, total, self.LABEL_STEP_DESTROYING, doc)
            doc.remove_label(label)
            current += 1
