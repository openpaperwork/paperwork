"""
Code for managing documents (not page individually ! see page.py for that)
"""

import os
import os.path
import time

from page import ScannedPage
from labels import Label
from util import dummy_progress_cb


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


class ScannedDoc(object):
    """
    Represents a document (aka a set of pages + labels).
    """

    LABEL_FILE = "labels"

    def __init__(self, docpath, docid=None):
        """
        Arguments:
            docpath --- For an existing document, the path to its folder. For
                a new one, the rootdir of all documents
            docid --- Document Id (ie folder name). Use None for a new document
        """
        if docid == None:
            self.docid = time.strftime("%Y%m%d_%H%M_%S")
            self.path = os.path.join(docpath, self.docid)
        else:
            self.docid = docid
            self.path = docpath

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

    def scan_next_page(self, device, ocrlang,
                       callback=dummy_progress_cb):
        """
        Scan a new page and append it as the last page of the document

        Arguments:
            device --- Sane device (see sane.open())
            ocrlang --- Language to specify to the OCR tool
            callback -- Progression indication callback (see
                util.dummy_progress_cb for the arguments to expected)
        """
        try:
            os.makedirs(self.path)
        except OSError:
            pass

        page_nb = self.nb_pages
        page = ScannedPage(self, page_nb)
        page.scan_page(device, ocrlang, callback)

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
                filepath = os.path.join(self.path, filename)
                print "Deleting file %s" % filepath
                os.unlink(filepath)
            for dirname in dirs:
                dirpath = os.path.join(self.path, dirname)
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
            callback(i, nb_pages, ScannedPage.SCAN_STEP_OCR, str(self))
            page = ScannedPage(self, i)
            page.redo_ocr(ocrlang)

    def add_label(self, label):
        """
        Add a label on the document.
        """
        if label in self.labels:
            return
        with open(os.path.join(self.path, self.LABEL_FILE), 'a') \
                as file_desc:
            file_desc.write("%s,%s\n" % (label.name, label.get_color_str()))

    def remove_label(self, to_remove):
        """
        Remove a label from the document. (-> rewrite the label file)
        """
        labels = self.labels
        labels.remove(to_remove)
        with open(os.path.join(self.path, self.LABEL_FILE), 'w') \
                as file_desc:
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
            with open(os.path.join(self.path, self.LABEL_FILE), 'r') \
                    as file_desc:
                for line in file_desc.readlines():
                    line = line.strip()
                    (label_name, label_color) = line.split(",")
                    labels.append(Label(name=label_name, color=label_color))
        except IOError, exc:
            print ("Error while reading labels from '%s': %s"
                   % (self.path, str(exc)))
        return labels

    labels = property(__get_labels)

    def update_label(self, old_label, new_label):
        print "%s : Updating label ([%s] -> [%s])" % (str(self), str(old_label),
                                                      str(new_label))
        labels = self.labels
        try:
            labels.remove(old_label)
        except ValueError, e:
            # this document doesn't have this label
            return;
        labels.append(new_label)
        with open(os.path.join(self.path, self.LABEL_FILE), 'w') \
                as file_desc:
            for label in labels:
                file_desc.write("%s,%s\n" % (label.name,
                                             label.get_color_str()))

    def __eq__(self, other):
        if None == other:
            return False
        return self.docid == other.docid

    def __ne__(self, other):
        return not self.__eq__(other)
