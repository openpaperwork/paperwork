#!/usr/bin/env python

import os
import os.path

class DocSearch(object):
    MIN_KEYWORD_LEN=3
    INDEX_STEP_READING = 0
    INDEX_STEP_SORTING = 1

    def __init__(self, rootdir):
        self.rootdir = rootdir
        self.keywords = []          # array of strings (sorted at the end of indexation)
        self.keywords_to_doc = {}   # keyword (string) -> array of path (string)

    def dummycallback(self, step, progression, total, filename=None):
        pass

    def _index_file(self, callback, filepath):
        print "Indexing %s" % filepath
        # TODO: fill in self.keywords_to_doc

    def _index_dir(self, callback, dirpath):
        for dpath in os.listdir(dirpath):
            if dpath[:1] == "." or dpath[-1:] == "~":
                continue
            elif os.path.isdir(os.path.join(dirpath, dpath)):
                self._index_dir(callback, os.path.join(dirpath, dpath))
            elif os.path.isfile(os.path.join(dirpath, dpath)) and dpath[-4:].lower() == ".txt":
                self._index_file(callback, os.path.join(dirpath, dpath))

    def _extract_keywords(self, callback):
        # TODO: fill in self.keywords with self.keywords_to_doc
        # TODO: sort self.keywords
        pass

    def index(self, callback = dummycallback):
        self._index_dir(callback, self.rootdir)
        self._extract_keywords(callback)

    def _get_suggestions(self, keyword):
        lkeyword = len(keyword)
        lkeywords = len(self.keywords)

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
            elif self.keywords[idx_min-1][:lkeyword] != keyword and self.keywords[idx_min][:lkeyword] == keyword:
                idx_min_found = False
            elif self.keywords[idx_min][:lkeyword] >= keyword:
                idx_min = idx_min - njump
            else:
                idx_min = idx_min + njump
            njump = (njump / 2) or 1

        if idx_min > lkeywords-1:
            return []

        # last element
        njump = ( (lkeywords - idx_min) / 4) or 1
        idx_max = ((lkeywords - idx_min) / 2) + idx_min
        idx_max_found = False

        while not idx_max_found:
            if idx_max <= 0 or idx_max >= lkeywords-1:
                idx_max_found = True
            elif self.keywords[idx_max+1][:lkeyword] != keyword and self.keywords[idx_max][:lkeyword] == keyword:
                idx_max_found = False
            elif self.keywords[idx_max][:lkeyword] <= keyword:
                idx_min = idx_min + njump
            else:
                idx_min = idx_min - njump
            njump = (njump / 2) or 1

        return self.keywords[idx_min:(idx_max+1)]


    def get_suggestions(self, keywords):
        suggestions = []
        for keyword in keywords:
            if len(keyword) < self.MIN_KEYWORD_LEN:
                continue
            suggestions.extend(self._get_suggestions(keyword))
        return suggestions

    def _get_documents(self, keyword):
        return self.keywords_to_doc[keyword]

    def get_documents(self, keywords):
        documents = None
        for keyword in keywords:
            if ( len(keyword) < self.MIN_KEYWORD_LEN ):
                return []
            docs = self._get_documents(keyword)
            if documents == None:
                documents = docs
            else:
                documents = [ val for val in documents if val in docs ] # intersection of both arrays

        if documents == None:
            return []
        return documents
