"""
Code for managing documents (not page individually ! see page.py for that)
"""

import codecs
import datetime
import os
import os.path
import time

from paperwork.model.labels import Label
from paperwork.model.page import ScannedPage
from paperwork.util import dummy_progress_cb


class ScannedPageListIterator(object):
    """
    Iterates on a page list
    """

    def __init__(self, page_list):
        self.idx = 0
        self.page_list = page_list

    def __iter__(self):
        return self

    def next(self):
        """
        Provide the next element of the list.
        """
        if self.idx >= len(self.page_list):
            raise StopIteration()
        page = self.page_list[self.idx]
        self.idx += 1
        return page


class ScannedPageList(object):
    """
    Page list. Page are accessed using [] operator.
    """

    def __init__(self, doc):
        self.doc = doc

    def __getitem__(self, idx):
        return ScannedPage(self.doc, idx)

    def __len__(self):
        return self.doc.nb_pages

    def __contains__(self, page):
        return (page.doc == self.doc and page.page_nb <= self.doc.nb_pages)

    def __eq__(self, other):
        return (self.doc == other.doc)

    def __iter__(self):
        return ScannedPageListIterator(self)


class ScannedDoc(object):
    """
    Represents a document (aka a set of pages + labels).
    """

    LABEL_FILE = "labels"
    DOCNAME_FORMAT = "%Y%m%d_%H%M_%S"

    def __init__(self, docpath, docid=None):
        """
        Arguments:
            docpath --- For an existing document, the path to its folder. For
                a new one, the rootdir of all documents
            docid --- Document Id (ie folder name). Use None for a new document
        """
        if docid == None:
            self.docid = time.strftime(self.DOCNAME_FORMAT)
            self.path = os.path.join(docpath, self.docid)
            self.__docid_hash = hash(self.docid)
        else:
            self.docid = docid
            self.path = docpath
            self.__docid_hash = hash(self.docid)

    def __str__(self):
        return self.docid

    def __get_nb_pages(self):
        """
        Compute the number of pages in the document. It basically counts
        how many JPG files there are in the document.
        """
        try:
            filelist = os.listdir(self.path)
            count = 0
            for filename in filelist:
                if (filename[-4:].lower() != "." + ScannedPage.EXT_IMG
                    or (filename[:len(ScannedPage.FILE_PREFIX)].lower() !=
                        ScannedPage.FILE_PREFIX)):
                    continue
                count += 1
            return count
        except OSError, exc:
            print ("Exception while trying to get the number of pages of "
                   "'%s': %s" % (self.docid, exc))
            return 0

    nb_pages = property(__get_nb_pages)

    def scan_single_page(self, scan_src, resolution,
                         ocrlang, scanner_calibration,
                         callback=dummy_progress_cb):
        """
        Scan a new page and append it as the last page of the document

        Arguments:
            scan_src --- see pyinsane.abstract_th.Scanner
            ocrlang --- Language to specify to the OCR tool
            callback -- Progression indication callback (see
                util.dummy_progress_cb for the arguments to expected)
        """
        callback(0, 100, ScannedPage.SCAN_STEP_SCAN)
        try:
            while True:
                scan_src.read()
                time.sleep(0)
        except EOFError:
            pass
        img = scan_src.get_img(0)

        try:
            os.makedirs(self.path)
        except OSError:
            pass

        page_nb = self.nb_pages
        page = ScannedPage(self, page_nb)
        page.make(img, ocrlang, resolution,
                  scanner_calibration, callback)

    def __get_pages(self):
        """
        Return a list of pages.
        Pages are instantiated on-the-fly.
        """
        return ScannedPageList(self)

    pages = property(__get_pages)

    def destroy(self):
        """
        Delete the document. The *whole* document. There will be no survivors.
        """
        print "Destroying doc: %s" % self.path
        for root, dirs, files in os.walk(self.path, topdown=False):
            for filename in files:
                filepath = os.path.join(root, filename)
                print "Deleting file %s" % filepath
                os.unlink(filepath)
            for dirname in dirs:
                dirpath = os.path.join(root, dirname)
                print "Deleting dir %s" % dirpath
                os.rmdir(dirpath)
        os.rmdir(self.path)
        print "Done"

    def print_page_cb(self, print_op, print_context, page_nb):
        """
        Called for printing operation by Gtk
        """
        page = ScannedPage(self, page_nb)
        page.print_page_cb(print_op, print_context)

    def redo_ocr(self, ocrlang, callback=dummy_progress_cb):
        """
        Run the OCR again on all the pages of the document

        Arguments
        """
        nb_pages = self.nb_pages
        for i in range(0, nb_pages):
            callback(i, nb_pages, ScannedPage.SCAN_STEP_OCR, self)
            page = ScannedPage(self, i)
            page.redo_ocr(ocrlang)

    def add_label(self, label):
        """
        Add a label on the document.
        """
        if label in self.labels:
            return
        with codecs.open(os.path.join(self.path, self.LABEL_FILE), 'a',
                        encoding='utf-8') as file_desc:
            file_desc.write("%s,%s\n" % (label.name, label.get_color_str()))

    def remove_label(self, to_remove):
        """
        Remove a label from the document. (-> rewrite the label file)
        """
        if not to_remove in self.labels:
            return
        labels = self.labels
        labels.remove(to_remove)
        with codecs.open(os.path.join(self.path, self.LABEL_FILE), 'w',
                        encoding='utf-8') as file_desc:
            for label in labels:
                file_desc.write("%s,%s\n" % (label.name,
                                             label.get_color_str()))

    def __get_labels(self):
        """
        Read the label file of the documents and extract all the labels

        Returns:
            An array of labels.Label objects
        """
        labels = []
        try:
            with codecs.open(os.path.join(self.path, self.LABEL_FILE), 'r',
                             encoding='utf-8') as file_desc:
                for line in file_desc.readlines():
                    line = line.strip()
                    (label_name, label_color) = line.split(",")
                    labels.append(Label(name=label_name, color=label_color))
        except IOError:
            pass
        return labels

    labels = property(__get_labels)

    def update_label(self, old_label, new_label):
        """
        Update a label

        Will go on each document, and replace 'old_label' by 'new_label'
        """
        print ("%s : Updating label ([%s] -> [%s])"
               % (str(self), str(old_label), str(new_label)))
        labels = self.labels
        try:
            labels.remove(old_label)
        except ValueError:
            # this document doesn't have this label
            return
        labels.append(new_label)
        with codecs.open(os.path.join(self.path, self.LABEL_FILE), 'w',
                        encoding='utf-8') as file_desc:
            for label in labels:
                file_desc.write("%s,%s\n" % (label.name,
                                             label.get_color_str()))

    def __doc_cmp(self, other):
        """
        Comparison function. Can be used to sort docs alphabetically.
        """
        if other == None:
            return -1
        return cmp(self.docid, other.docid)

    def __lt__(self, other):
        return self.__doc_cmp(other) < 0

    def __gt__(self, other):
        return self.__doc_cmp(other) > 0

    def __eq__(self, other):
        return self.__doc_cmp(other) == 0

    def __le__(self, other):
        return self.__doc_cmp(other) <= 0

    def __ge__(self, other):
        return self.__doc_cmp(other) >= 0

    def __ne__(self, other):
        return self.__doc_cmp(other) != 0

    def __hash__(self):
        return self.__docid_hash

    def __get_name(self):
        """
        Returns the localized name of the document (see l10n)
        """
        try:
            datetime_obj = datetime.datetime.strptime(
                    self.docid, self.DOCNAME_FORMAT)
        except ValueError, exc:
            print ("Unable to parse document id [%s]: %s"
                   % (self.docid, str(exc)))
            return self.docid
        return datetime_obj.strftime("%x %X")

    name = property(__get_name)

    def __get_keywords(self):
        """
        Yield all the keywords contained in the document.
        """
        for page in self.pages:
            for keyword in page.keywords:
                yield(keyword)

    keywords = property(__get_keywords)
