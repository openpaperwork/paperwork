#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
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
Also everything related to indexation and searching in the documents (+
suggestions)
"""

import gc
import logging
import os.path

import gi
from gi.repository import GObject

from . import fs
from .index import PaperworkIndexClient
from .util import dummy_progress_cb

gi.require_version('PangoCairo', '1.0')
gi.require_version('Poppler', '0.18')

logger = logging.getLogger(__name__)


DEFAULT_INDEX_CLIENT = PaperworkIndexClient()


class DummyDocSearch(object):
    """
    Dummy doc search object.

    Instantiating a DocSearch object takes time (the time to rereard the
    index). So you can use this object instead during this time as a
    placeholder
    """
    docs = []
    label_list = []

    def __init__(self):
        self.fs = fs.GioFileSystem()

    @staticmethod
    def get_doc_examiner(*args, **kwargs):
        """ Do nothing """
        assert()

    @staticmethod
    def get_index_updater(*args, **kwargs):
        """ Do nothing """
        assert()

    @staticmethod
    def find_suggestions(*args, **kwargs):
        """ Do nothing """
        return []

    @staticmethod
    def find_documents(*args, **kwargs):
        """ Do nothing """
        return []

    @staticmethod
    def create_label(*args, **kwargs):
        """ Do nothing """
        assert()

    @staticmethod
    def add_label(*args, **kwargs):
        """ Do nothing """
        assert()

    @staticmethod
    def remove_label(*args, **kwargs):
        """ Do nothing """
        assert()

    @staticmethod
    def update_label(*args, **kwargs):
        """ Do nothing """
        assert()

    @staticmethod
    def destroy_label(*args, **kwargs):
        """ Do nothing """
        assert()

    @staticmethod
    def destroy_index():
        """ Do nothing """
        assert()

    @staticmethod
    def is_hash_in_index(*args, **kwargs):
        """ Do nothing """
        assert()

    @staticmethod
    def guess_labels(*args, **kwargs):
        """ Do nothing """
        assert()

    @staticmethod
    def get(*args, **kwargs):
        """ Do nothing """
        return None

    @staticmethod
    def get_doc_from_docid(docid, doc_type_name=None, inst=True):
        """ Do nothing """
        return None

    def set_language(self, language):
        return

    @staticmethod
    def close(*args, **kwargs):
        """ Do nothing """
        return

    @staticmethod
    def stop(*args, **kwargs):
        """ Do nothing """
        return


class DocDirExaminer(GObject.GObject):
    """
    Examine a directory containing documents. It looks for new documents,
    modified documents, or deleted documents.
    """
    def __init__(self, docsearch):
        GObject.GObject.__init__(self)
        self.docsearch = docsearch

    def examine_rootdir(self,
                        on_new_doc,
                        on_doc_modified,
                        on_doc_deleted,
                        on_doc_unchanged,
                        progress_cb=dummy_progress_cb):
        """
        Examine the rootdir.
        Calls on_new_doc(doc), on_doc_modified(doc), on_doc_deleted(docid)
        every time a new, modified, or deleted document is found
        """

        count = self.docsearch.index.start_examine_rootdir()

        progress = 0
        while True:
            (status, doc) = self.docsearch.index.continue_examine_rootdir()
            if status == 'end':
                break
            elif status == 'modified':
                on_doc_modified(doc)
            elif status == 'unchanged':
                on_doc_unchanged(doc)
            elif status == 'new':
                on_new_doc(doc)
            progress_cb(progress, count,
                        DocSearch.INDEX_STEP_CHECKING, doc)
            progress += 1

        while True:
            (status, doc) = self.docsearch.index.continue_examine_rootdir2()
            if status == 'end':
                break
            on_doc_deleted(doc)

        progress_cb(1, 1, DocSearch.INDEX_STEP_CHECKING)
        self.docsearch.index.end_examine_rootdir()


class DocIndexUpdater(GObject.GObject):
    """
    Update the index content.
    Don't forget to call commit() to apply the changes
    """
    def __init__(self, docsearch, optimize, progress_cb=dummy_progress_cb):
        self.docsearch = docsearch
        self.optimize = optimize
        self.progress_cb = progress_cb

    def add_doc(self, doc, index_update=True, label_guesser_update=True):
        """
        Add a document to the index
        """
        logger.info("Indexing new doc: %s" % doc)
        doc = doc.clone()  # make sure it can be serialized safely
        self.docsearch.index.add_doc(doc, index_update=index_update,
                                     label_guesser_update=label_guesser_update)

    def upd_doc(self, doc, index_update=True, label_guesser_update=True):
        """
        Update a document in the index
        """
        logger.info("Updating modified doc: %s" % doc)
        doc = doc.clone()  # make sure it can be serialized safely
        self.docsearch.index.upd_doc(doc, index_update=index_update,
                                     label_guesser_update=label_guesser_update)

    def del_doc(self, doc):
        """
        Delete a document
        """
        logger.info("Removing doc from the index: %s" % doc)
        doc = doc.clone()  # make sure it can be serialized safely
        self.docsearch.index.del_doc(doc)

    def commit(self, index_update=True, label_guesser_update=True):
        """
        Apply the changes to the index
        """
        logger.info("Index: Commiting changes")
        self.docsearch.index.commit(index_update=index_update,
                                    label_guesser_update=label_guesser_update)

    def cancel(self):
        """
        Forget about the changes
        """
        logger.info("Index: Index update cancelled")
        self.docsearch.index.cancel()


class DocSearch(object):
    """
    Index a set of documents. Can provide:
        * documents that match a list of keywords
        * suggestions for user input.
        * instances of documents
    """

    INDEX_STEP_LOADING = "loading"
    INDEX_STEP_CHECKING = "checking"
    INDEX_STEP_READING = "checking"
    INDEX_STEP_COMMIT = "commit"
    LABEL_STEP_UPDATING = "label updating"
    LABEL_STEP_DESTROYING = "label deletion"

    def __init__(self, rootdir, indexdir=None, language=None,
                 use_default_index_client=True):
        """
        Index files in rootdir (see constructor)
        """
        if use_default_index_client:
            self.index = DEFAULT_INDEX_CLIENT
        else:
            self.index = PaperworkIndexClient()

        self.fs = fs.GioFileSystem()
        self.rootdir = self.fs.safe(rootdir)

        localdir = os.path.expanduser("~/.local")
        if indexdir is None:
            base_data_dir = os.getenv(
                "XDG_DATA_HOME",
                os.path.join(localdir, "share")
            )
            indexdir = os.path.join(base_data_dir, "paperwork")

        indexdir = os.path.join(indexdir, "index")
        label_guesser_dir = os.path.join(indexdir, "label_guessing")
        self.index.open(localdir, base_data_dir, indexdir, label_guesser_dir,
                        rootdir, language=language)

    def set_language(self, language):
        self.index.set_language(language)

    def get_doc_examiner(self):
        """
        Return an object useful to find added/modified/removed documents
        """
        return DocDirExaminer(self)

    def get_index_updater(self, optimize=True):
        """
        Return an object useful to update the content of the index

        Note that this object is only about modifying the index. It is not
        made to modify the documents themselves.
        Some helper methods, with more specific goals, may be available for
        what you want to do.
        """
        return DocIndexUpdater(self, optimize)

    def guess_labels(self, doc):
        """
        return a prediction of label names
        """
        doc = doc.clone()  # make sure it can be serialized safely
        return self.index.guess_labels(doc)

    def reload_index(self, progress_cb=dummy_progress_cb):
        """
        Read the index, and load the document list from it

        Arguments:
            callback --- called during the indexation (may be called *often*).
                step : DocSearch.INDEX_STEP_READING or
                    DocSearch.INDEX_STEP_SORTING
                progression : how many elements done yet
                total : number of elements to do
                document (only if step == DocSearch.INDEX_STEP_READING): file
                    being read
        """
        nb_results = self.index.start_reload_index()
        progress = 0
        while self.index.continue_reload_index():
            progress_cb(progress, nb_results, self.INDEX_STEP_LOADING)
            progress += 1
        progress_cb(1, 1, self.INDEX_STEP_LOADING)
        self.index.end_reload_index()

    def __get_all_docs(self):
        """
        Return all the documents. Beware, they are unsorted.
        """
        return self.index.get_all_docs()

    docs = property(__get_all_docs)

    @property
    def nb_docs(self):
        return self.index.get_nb_docs()

    def get(self, obj_id):
        """
        Get a document or a page using its ID
        Won't instantiate them if they are not yet available
        """
        return self.index.get(obj_id)

    def get_doc_from_docid(self, docid, doc_type_name=None, inst=True):
        return self.index.get_doc_from_docid(docid, doc_type_name=doc_type_name,
                                             inst=inst)

    def find_documents(self, sentence, limit=None, must_sort=True,
                       search_type='fuzzy'):
        return self.index.find_documents(sentence, limit=limit,
                                         must_sort=must_sort,
                                         search_type=search_type)

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
        return self.index.find_suggestions(sentence)

    def create_label(self, label, doc=None, callback=dummy_progress_cb):
        """
        Create a new label

        Arguments:
            doc --- first document on which the label must be added (required
                    for now)
        """
        if doc:
            clone = doc.clone()  # make sure it's serializable
        r = self.index.create_label(label, doc=clone)
        return r

    def add_label(self, doc, label, update_index=True):
        """
        Add a label on a document.

        Arguments:
            label --- The new label (see labels.Label)
            doc --- The first document on which this label has been added
        """
        doc = doc.clone()  # make sure it's serializable
        r = self.index.add_label(doc, label, update_index=update_index)
        return r

    def remove_label(self, doc, label, update_index=True):
        """
        Remove a label from a doc. Takes care of updating the index
        """
        doc = doc.clone()  # make sure it's serializable
        r = self.index.remove_label(doc, label, update_index=update_index)
        return r

    def update_label(self, old_label, new_label, callback=dummy_progress_cb):
        """
        Replace 'old_label' by 'new_label' on all the documents. Takes care of
        updating the index.
        """
        current = 0
        total = self.get_nb_docs()
        self.index.start_update_label(old_label, new_label)
        while True:
            (op, doc) = self.index.continue_update_label()
            if op == 'end':
                break
            callback(current, total, self.LABEL_STEP_UPDATING, doc)
            current += 1
        self.index.end_update_label()

    def destroy_label(self, label, callback=dummy_progress_cb):
        """
        Remove the label 'label' from all the documents. Takes care of updating
        the index.
        """
        current = 0
        total = self.get_nb_docs()
        self.index.start_destroy_label(label)
        while True:
            (op, doc) = self.index.continue_destroy_label()
            if op == 'end':
                break
            callback(current, total, self.LABEL_STEP_DESTROYING, doc)
            current += 1
        self.index.end_destroy_label()

    def close(self):
        self.index.close()

    def stop(self):
        self.index.stop()

    def gc(self):
        gc.collect()
        self.index.gc()

    def destroy_index(self):
        """
        Destroy the index. Don't use this DocSearch object anymore after this
        call. Index will have to be rebuilt from scratch
        """
        self.gc()
        self.index.destroy_index()

    def is_hash_in_index(self, filehash):
        """
        Check if there is a document using this file hash
        """
        return self.index.is_hash_in_index(filehash)

    def __get_label_list(self):
        return self.index.get_label_list()

    def __set_label_list(self, label_list):
        return self.index.set_label_list(label_list)

    label_list = property(__get_label_list, __set_label_list)
