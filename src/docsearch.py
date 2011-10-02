#!/usr/bin/env python

import codecs
import os
import os.path
import time
import threading

from util import strip_accents
from doc import ScannedDoc

class DocSearch(object):
    MIN_KEYWORD_LEN = 2

    INDEX_STEP_READING  = 0
    INDEX_STEP_SORTING  = 1

    def __init__(self, rootdir, callback = None):
        """
        Index files in rootdir (see constructor)

        Arguments:
            callback --- called during the indexation (may be called *often*).
                step : DocSearch.INDEX_STEP_READING or DocSearch.INDEX_STEP_SORTING
                progression : how many elements done yet
                total : number of elements to do
                document (only if step == DocSearch.INDEX_STEP_READING): file being read
        """
        if callback == None:
            callback = lambda step, progression, total, document=None: None
        self.rootdir = rootdir
        self._index(callback)

    def _simplify(self, keyword):
        keyword = keyword.strip()
        keyword = strip_accents(keyword)
        keyword = keyword.lower()
        return keyword

    def _index_page(self, docpath, page):
        print "Indexing '%s'" % str(page)
        for word in page.get_keywords():
            word = self._simplify(word)
            if len(word) < self.MIN_KEYWORD_LEN:
                continue
            if self.keywords_to_doc.has_key(word):
                if not docpath in self.keywords_to_doc[word]:
                    self.keywords_to_doc[word].append(docpath)
            else:
                self.keywords_to_doc[word] = [ docpath ]

    def _index_dir(self, callback, dirpath, progression = 0, total = 0):
        dlist = os.listdir(dirpath)
        dlist.sort()
        if total == 0:
            progression = 0
            total = len(dlist)
        page_nb = 0
        for dpath in dlist:
            if dpath[:1] == "." or dpath[-1:] == "~":
                continue
            elif os.path.isdir(os.path.join(dirpath, dpath)):
                callback(self.INDEX_STEP_READING, progression, total, dpath)
                self._index_dir(callback, os.path.join(dirpath, dpath), progression, total)
                progression = progression + 1
            elif os.path.isfile(os.path.join(dirpath, dpath)) and dpath[-4:].lower() == ".txt":
                page_nb += 1
                self._index_page(dirpath, ScannedDoc(dirpath, dirpath).get_page(page_nb))

    def _docpath_to_id(self, docpath):
        return os.path.split(docpath)[1]

    def _extract_docpaths(self, callback):
        callback(self.INDEX_STEP_SORTING, 0, 3)
        for docs in self.keywords_to_doc.values():
            for docpath in docs:
                docid = self._docpath_to_id(docpath)
                if not self.docpaths.has_key(docid):
                    self.docpaths[docid] = docpath

    def _extract_keywords(self, callback):
        callback(self.INDEX_STEP_SORTING, 1, 3)
        self.keywords = self.keywords_to_doc.keys()
        callback(self.INDEX_STEP_SORTING, 2, 3)
        self.keywords.sort()

    def _index(self, callback = None):
        self.keywords = []          # array of strings (sorted at the end of indexation)
        self.docpaths = {}          # doc id (string) -> full path
        self.keywords_to_doc = {}   # keyword (string) -> array of path

        self._index_dir(callback, self.rootdir)
        self._extract_docpaths(callback)
        self._extract_keywords(callback)

    def index_page(self, page):
        docpath = page.get_doc().docpath
        self._index_page(docpath, page)
        # remake these two:
        self._extract_docpaths(ScannedDoc.dummy_callback)
        self._extract_keywords(ScannedDoc.dummy_callback)

    def _get_keyword_suggestions(self, keyword):
        neg = (keyword[:1] == "!")
        if neg:
            keyword = keyword[1:]
        keyword = self._simplify(keyword)

        lkeyword = len(keyword)
        lkeywords = len(self.keywords)

        if lkeyword < self.MIN_KEYWORD_LEN:
            return []

        # the array is sorted. So we use dichotomy to
        # figure the position of the first element matching the keyword
        # and the position of the last one

        # first element
        njump = (lkeywords / 4) or 1
        idx_min = lkeywords / 2
        idx_min_found = False

        while not idx_min_found:
            if idx_min <= 0 or idx_min > lkeywords-1:
                idx_min_found = True
            elif self.keywords[idx_min-1][:lkeyword] < keyword and self.keywords[idx_min][:lkeyword] > keyword:
                print "No suggestion found for '%s'" % keyword
                return []
            elif self.keywords[idx_min-1][:lkeyword] != keyword and self.keywords[idx_min][:lkeyword] == keyword:
                idx_min_found = True
            elif self.keywords[idx_min][:lkeyword] >= keyword:
                idx_min = idx_min - njump
            else:
                idx_min = idx_min + njump
            njump = (njump / 2) or 1

        if idx_min > lkeywords-1:
            print "No suggestion found for '%s'" % keyword
            return []

        # last element
        njump = ( (lkeywords - idx_min) / 4) or 1
        idx_max = ((lkeywords - idx_min) / 2) + idx_min
        idx_max_found = False

        while not idx_max_found:
            if idx_max <= 0 or idx_max >= lkeywords-1:
                idx_max_found = True
            elif self.keywords[idx_max+1][:lkeyword] != keyword and self.keywords[idx_max][:lkeyword] == keyword:
                idx_max_found = True
            elif self.keywords[idx_max][:lkeyword] <= keyword:
                idx_max = idx_max + njump
            else:
                idx_max = idx_max - njump
            njump = (njump / 2) or 1

        results = self.keywords[idx_min:(idx_max+1)]

        if neg:
            results = [ ("!%s" % (result)) for result in results ]

        print "Got %d suggestions for [%s]" % (len(results), keyword)

        return results

    def _get_suggestions(self, keywords):
        if len(keywords) <= 0:
            return []

        # search suggestion for the first keywords
        first_keyword_suggestions = self._get_keyword_suggestions(keywords[0])
        if (len(keywords) <= 1):
            return [ [ word ] for word in first_keyword_suggestions ]

        results = []

        # .. and for all the remaining keywords
        # XXX(Jflesch): recursivity
        other_keywords_suggestions = self._get_suggestions(keywords[1:])

        for first_keyword_suggestion in first_keyword_suggestions:
            for suggestion in other_keywords_suggestions:
                suggestion = suggestion[:]
                suggestion.insert(0, first_keyword_suggestion)
                # immediatly look if it has matching documents
                if len(suggestion) > 1 and len(self.get_documents(suggestion)) <= 0:
                    print "Suggestion %s dropped" % (suggestion)
                    continue
                print "Keeping %s for now" % (suggestion)
                results.append(suggestion)

        return results

    def get_suggestions(self, keywords):
        """
        Search all possible suggestions. Suggestions returned always have at least
        one document matching.

        Arguments:
            keywords --- array of keyword for which we want suggestions
        Return:
            An array of sets of keywords. Each set of keywords is a suggestion.
        """
        results = self._get_suggestions(keywords)
        try:
            results.remove(keywords) # remove strict match if it is here
        except ValueError, e:
            pass
        results.sort()
        return results

    def _get_documents(self, keyword):
        try:
            return self.keywords_to_doc[keyword]
        except KeyError:
            return []

    def get_documents(self, keywords):
        positive_keywords = []
        negative_keywords = []

        print "Looking for documents containing %s" % (keywords)

        for keyword in keywords:
            if keyword[:1] != "!":
                positive_keywords.append(keyword)
            else:
                negative_keywords.append(keyword[1:])

        if (len(positive_keywords) == 1 and positive_keywords[0] == u"*"):
            print "Returning all documents"
            dlist = os.listdir(self.rootdir)
            for dirpath in dlist:
                if not os.path.isdir(os.path.join(self.rootdir, dirpath)):
                    dlist.remove(dirpath)
            dlist.sort()
            return dlist
        documents = None
        for keyword in positive_keywords:
            if ( len(keyword) < self.MIN_KEYWORD_LEN ):
                return []
            keyword = self._simplify(keyword)
            docs = self._get_documents(keyword)
            if documents == None:
                documents = docs
            else:
                documents = [ val for val in documents if val in docs ] # intersection of both arrays

        if documents == None:
            return []

        print "Found %d documents" % (len(documents))

        for keyword in negative_keywords:
            if ( len(keyword) < self.MIN_KEYWORD_LEN ):
                return []
            keyword = self._simplify(keyword)
            docs = self._get_documents(keyword)
            print "Found %d documents to remove" % (len(documents))
            for doc in docs:
                try:
                    documents.remove(doc)
                except ValueError, e:
                    pass

        # 'documents' contains the whole paths, but we actually identify documents
        # only by the directory in which they are
        short_docs = []
        for docpath in documents:
            try:
                docid = self._docpath_to_id(docpath)
                short_docs.append(docid)
            except Exception, e:
                print "Warning: Invalid document path: %s (%s)" % (docpath, e)

        short_docs.sort()
        return short_docs

    def get_doc(self, docid):
        return ScannedDoc(self.docpaths[docid], docid)

    def redo_ocr(self, callback, ocrlang):
        print "Redoing OCR of all documents ..."

        MAX_THREADS = 4
        SLEEP_TIME = 0.5

        dlist = os.listdir(self.rootdir)
        threads = []
        remaining = dlist[:]

        while (len(remaining) > 0 or len(threads) > 0):
            for thread in threads:
                if not thread.is_alive():
                    threads.remove(thread)
            while (len(threads) < MAX_THREADS and len(remaining) > 0):
                docid = remaining.pop()
                docpath = os.path.join(self.rootdir, docid)
                doc = ScannedDoc(docpath, docid)
                thread = threading.Thread(target = doc.redo_ocr, args = [ ocrlang ], name = docid)
                thread.start()
                threads.append(thread)
                callback(self.INDEX_STEP_READING, len(dlist) - len(remaining), len(dlist), docid)
            time.sleep(SLEEP_TIME)
        print "OCR of all documents done"

