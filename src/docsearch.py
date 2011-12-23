"""
Contains all the code relative to keyword and document list management list.
"""

import os
import os.path
import time
import threading

from doc import ScannedDoc
from util import dummy_progress_cb
from util import strip_accents

class DocIter(object):
    """
    Allows to iterate on all the documents easily
    """
    def __init__(self, docsearch):
        self.docsearch = docsearch
        self.dociter = iter(docsearch.docids)

    def __iter__(self):
        return self

    def next(self):
        next_docid = self.dociter.next()
        return ScannedDoc(self.docsearch.get_docpath_by_docid(next_docid),
                          next_docid)

class DocList(object):
    """
    Doc list. Docs are accessed using [] operator. The key is the document id
    (for instance, '20110929_1233_0900')
    """
    def __init__(self, docsearch):
        self.docsearch = docsearch

    def __getitem__(self, docid):
        return ScannedDoc(self.docsearch.get_docpath_by_docid(docid), docid)

    def __eq__(self, other):
        return self.docsearch.rootdir == other.docsearch.rootdir

    def __iter__(self):
        return DocIter(self.docsearch)

    def __len__(self):
        return len(os.listdir(self.docsearch.rootdir))


class DocSearch(object):
    """
    Index a set of documents. Can provide:
        * documents that match a list of keywords
        * suggestions for user input.
        * instances of documents
    """

    MIN_KEYWORD_LEN = 2
    INDEX_STEP_READING = "reading"
    INDEX_STEP_SORTING = "sorting"
    LABEL_STEP_UPDATING = "label updating"
    LABEL_STEP_DESTROYING = "label deletion"
    OCR_MAX_THREADS = 4
    OCR_SLEEP_TIME = 0.5

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
        self.__keywords = []                # array of strings (sorted)
        self.__docids_to_docpath = {}       # doc id (string) -> full path
        self.__keywords_to_docpaths = {}    # keyword (string) -> array of path
        self.label_list = []

        self.__index(callback)

    def __reset_data(self):
        """
        Purge the lists of documents and keywords
        """
        self.__keywords = []
        self.__docids_to_docpath = {}
        self.__keywords_to_docpaths = {}
        self.label_list = []

    @staticmethod
    def __simplify(keyword):
        """
        Simplify the keyword
        * Strip white spaces
        * Strip accents
        * And lower case it
        """
        keyword = keyword.strip()
        keyword = strip_accents(keyword)
        keyword = keyword.lower()
        return keyword

    def __index_keyword(self, keyword, docpath):
        """
        Add the given keywords to self.__keywords_to_docpaths
        """
        if keyword in self.__keywords_to_docpaths:
            if not docpath in self.__keywords_to_docpaths[keyword]:
                self.__keywords_to_docpaths[keyword].append(docpath)
        else:
            self.__keywords_to_docpaths[keyword] = [docpath]

    def __index_doc(self, doc):
        for word in doc.keywords:
            word = self.__simplify(word)
            if len(word) < self.MIN_KEYWORD_LEN:
                continue
            self.__index_keyword(word, doc.path)

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

        page_nb = 0
        for dpath in dlist:
            if dpath[:1] == "." or dpath[-1:] == "~":
                progression = progression + 1
                continue
            elif os.path.isdir(os.path.join(dirpath, dpath)):
                doc = ScannedDoc(os.path.join(dirpath, dpath), dpath)
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

    def __extract_docpaths(self, callback=dummy_progress_cb):
        """
        Create an index docid->docpaths (self.__docids_to_docpath) based on
        self.__keywords_to_docpaths
        """
        callback(0, 3, self.INDEX_STEP_SORTING)
        for docs in self.__keywords_to_docpaths.values():
            for docpath in docs:
                docid = self.__docpath_to_id(docpath)
                if not docid in self.__docids_to_docpath:
                    self.__docids_to_docpath[docid] = docpath

    def __extract_keywords(self, callback=dummy_progress_cb):
        """
        Extract and index all the keywords from all the documents in
        self.rootdir.
        """
        callback(1, 3, self.INDEX_STEP_SORTING)
        self.__keywords = self.__keywords_to_docpaths.keys()
        for label in self.label_list:
            if not label.name in self.__keywords:
                self.__keywords.append(label.name)
        callback(2, 3, self.INDEX_STEP_SORTING)
        self.__keywords.sort()

    def __index(self, callback=dummy_progress_cb):
        """
        Index all the documents in self.rootdir.

        Arguments:
            callback --- progression indicator callback (see
                util.dummy_progress_cb)
        """
        self.__reset_data()
        self.__index_dir(self.rootdir, callback=callback)
        self.__extract_docpaths(callback)
        self.__extract_keywords(callback)

    def index_page(self, page):
        """
        Extract all the keywords from the given page

        Arguments:
            page --- from which keywords must be extracted
        """
        self.__index_page(page.doc.path, page)
        # remake these two:
        self.__extract_docpaths(dummy_progress_cb)
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
        keyword = self.__simplify(keyword)

        lkeyword = len(keyword)
        lkeywords = len(self.__keywords)

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
        if (len(keywords) <= 1):
            return [[word] for word in first_keyword_suggestions]

        results = []

        # .. and for all the remaining keywords
        # XXX(Jflesch): recursivity
        other_keywords_suggestions = self.__find_suggestions(keywords[1:])

        for first_keyword_suggestion in first_keyword_suggestions:
            for suggestion in other_keywords_suggestions:
                suggestion = suggestion[:]
                suggestion.insert(0, first_keyword_suggestion)
                # immediatly look if it has matching documents
                if (len(suggestion) > 1
                    and len(self.find_documents(suggestion)) <= 0):
                    continue
                results.append(suggestion)

        return results

    def find_suggestions(self, keywords):
        """
        Search all possible suggestions. Suggestions returned always have at
        least one document matching.

        Arguments:
            keywords --- array of keyword (strings) for which we want
                suggestions
        Return:
            An array of sets of keywords. Each set of keywords (-> one string)
            is a suggestion.
        """
        results = self.__find_suggestions(keywords)
        try:
            results.remove(keywords)    # remove strict match if it is here
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
            An array of document id (strings)
        """
        try:
            return self.__keywords_to_docpaths[keyword]
        except KeyError:
            return []

    def find_documents(self, keywords):
        """
        Returns all the documents matching the given keywords

        Arguments:
            keywords --- array of keywords (string)

        Returns:
            An array of document id (strings)
        """
        positive_keywords = []
        negative_keywords = []

        print "Looking for documents containing %s" % (keywords)

        for keyword in keywords:
            if keyword[:1] != "!":
                positive_keywords.append(keyword)
            else:
                negative_keywords.append(keyword[1:])

        if (len(positive_keywords) == 1
            and unicode(positive_keywords[0]) == u"*"):
            print "Returning all documents"
            doclist = self.__docids_to_docpath.keys()
            doclist.sort()
            return doclist
        documents = None
        for keyword in positive_keywords:
            if (len(keyword) < self.MIN_KEYWORD_LEN):
                return []
            keyword = self.__simplify(keyword)
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
            if (len(keyword) < self.MIN_KEYWORD_LEN):
                return []
            keyword = self.__simplify(keyword)
            docs = self.__find_documents(keyword)
            print "Found %d documents to remove" % (len(documents))
            for doc in docs:
                try:
                    documents.remove(doc)
                except ValueError:
                    pass

        # 'documents' contains the whole paths, but we actually identify
        # documents only by the directory in which they are
        short_docs = []
        for docpath in documents:
            docid = self.__docpath_to_id(docpath)
            short_docs.append(docid)

        short_docs.sort()
        return short_docs

    def get_docpath_by_docid(self, docid):
        """
        Returns a documents path for a specific document id.

        Arguments:
            docid --- Document id. For instance '20110722_1233_56'

        Returns:
                Document path. For instance
                '/home/jflesch/papers/20110722_1233_56'
        """
        return self.__docids_to_docpath[docid]

    def __get_docs(self):
        """
        Returns an object associating docid to documents (doc.ScannedDoc).
        Documents are instanciated on-the-fly.
        """
        return DocList(self)

    docs = property(__get_docs)

    def __get_docids(self):
        """
        Returns all the known docpaths
        """
        return self.__docids_to_docpath.keys()

    docids = property(__get_docids)

    def add_label(self, label, doc):
        """
        Add a new label to the list of known labels.

        Arguments:
            label --- The new label (see labels.Label)
            doc --- The first document on which this label has been added
        """
        label_name = self.__simplify(unicode(label.name))
        self.__index_keyword(label_name, doc.path)
        if not label_name in self.__keywords:
            self.__keywords.append(label_name)
            self.__keywords.sort()
        if not label in self.label_list:
            self.label_list.append(label)
            self.label_list.sort()

    def redo_ocr(self, progress_callback, ocrlang):
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

        while (len(remaining) > 0 or len(threads) > 0):
            for thread in threads:
                if not thread.is_alive():
                    threads.remove(thread)
            while (len(threads) < self.OCR_MAX_THREADS and len(remaining) > 0):
                docid = remaining.pop()
                docpath = os.path.join(self.rootdir, docid)
                doc = ScannedDoc(docpath, docid)
                thread = threading.Thread(target=doc.redo_ocr,
                                          args=[ocrlang], name=docid)
                thread.start()
                threads.append(thread)
                progress_callback(len(dlist) - len(remaining),
                                  len(dlist), self.INDEX_STEP_READING,
                                  docid)
            time.sleep(self.OCR_SLEEP_TIME)
        print "OCR of all documents done"

    def update_label(self, old_label, new_label, callback=dummy_progress_cb):
        self.label_list.remove(old_label)
        if new_label not in self.label_list:
            self.label_list.append(new_label)
        self.label_list.sort()
        current = 0
        total = len(self.docs)
        for doc in self.docs:
            callback(current, total, self.LABEL_STEP_UPDATING, str(doc))
            doc.update_label(old_label, new_label)
            current += 1

    def destroy_label(self, label, callback=dummy_progress_cb):
        self.label_list.remove(label)
        current = 0
        total = len(self.docs)
        for doc in self.docs:
            callback(current, total, self.LABEL_STEP_DESTROYING, str(doc))
            doc.remove_label(label)
            current += 1
