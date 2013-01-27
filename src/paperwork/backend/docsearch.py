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

import whoosh.fields
import whoosh.index

from paperwork.backend.img.doc import ImgDoc
from paperwork.backend.img.doc import is_img_doc
from paperwork.backend.pdf.doc import PdfDoc
from paperwork.backend.pdf.doc import is_pdf_doc
from paperwork.util import dummy_progress_cb
from paperwork.util import MIN_KEYWORD_LEN
from paperwork.util import mkdir_p
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
        base_indexdir = os.getenv("XDG_DATA_HOME",
                                  os.path.expanduser("~/.local/share"))
        self.indexdir = os.path.join(base_indexdir, "paperwork", "index")
        mkdir_p(self.indexdir)

        try:
            print ("Opening index dir '%s' ..." % self.indexdir)
            self.index = whoosh.index.open_dir(self.indexdir)
        except whoosh.index.EmptyIndexError, exc:
            print ("Failed to open index '%s'" % self.indexdir)
            print ("Will try to create a new one")
            schema = whoosh.fields.Schema(
                docid=whoosh.fields.ID,
                content=whoosh.fields.TEXT,
                labels=whoosh.fields.KEYWORD,
                last_read=whoosh.fields.DATETIME,
                thumbnail=whoosh.fields.STORED,
            )
            self.index = whoosh.index.create_in(self.indexdir, schema)
            print ("Index '%s' created" % self.indexdir)


    def index_page(self, page):
        """
        Extract all the keywords from the given page

        Arguments:
            page --- from which keywords must be extracted
        """
        # TODO
        pass

    def __get_all_docs(self):
        # TODO
        return []

    docs = property(__get_all_docs)

    def __get_all_labels(self):
        # TODO
        return []

    label_list = property(__get_all_labels)

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
        # TODO
        return []

    def find_documents(self, sentence):
        """
        Returns all the documents matching the given keywords

        Arguments:
            keywords --- keywords (single string)

        Returns:
            An array of document id (strings)
        """
        # TODO
        return []

    def add_label(self, label, doc):
        """
        Add a new label to the list of known labels.

        Arguments:
            label --- The new label (see labels.Label)
            doc --- The first document on which this label has been added
        """
        # TODO: Index
        # TODO: Add label to the global list (if any)
        pass

    def update_label(self, old_label, new_label, callback=dummy_progress_cb):
        """
        Replace 'old_label' by 'new_label' on all the documents
        """
        # TODO
        pass

    def destroy_label(self, label, callback=dummy_progress_cb):
        """
        Remove the label 'label' from all the documents
        """
        # TODO
        pass

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

