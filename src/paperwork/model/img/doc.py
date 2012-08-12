"""
Code for managing documents (not page individually ! see page.py for that)
"""

import codecs
import datetime
import os
import os.path
import time

from paperwork.model.common.doc import BasicDoc
from paperwork.model.img.page import ImgPage
from paperwork.util import dummy_progress_cb


class _ImgPageListIterator(object):
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


class _ImgPageList(object):
    """
    Page list. Page are accessed using [] operator.
    """

    def __init__(self, doc):
        self.doc = doc

    def __getitem__(self, idx):
        return ImgPage(self.doc, idx)

    def __len__(self):
        return self.doc.nb_pages

    def __contains__(self, page):
        return (page.doc == self.doc and page.page_nb <= self.doc.nb_pages)

    def __eq__(self, other):
        return (self.doc == other.doc)

    def __iter__(self):
        return _ImgPageListIterator(self)


class ImgDoc(BasicDoc):
    """
    Represents a document (aka a set of pages + labels).
    """
    can_edit = True

    def __init__(self, docpath, docid=None):
        """
        Arguments:
            docpath --- For an existing document, the path to its folder. For
                a new one, the rootdir of all documents
            docid --- Document Id (ie folder name). Use None for a new document
        """
        BasicDoc.__init__(self, docpath, docid)

    def __get_nb_pages(self):
        """
        Compute the number of pages in the document. It basically counts
        how many JPG files there are in the document.
        """
        try:
            filelist = os.listdir(self.path)
            count = 0
            for filename in filelist:
                if (filename[-4:].lower() != "." + ImgPage.EXT_IMG
                    or (filename[:len(ImgPage.FILE_PREFIX)].lower() !=
                        ImgPage.FILE_PREFIX)):
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
        callback(0, 100, ImgPage.SCAN_STEP_SCAN)
        nb_pages = scan_src.get_nb_img()
        try:
            while True:
                scan_src.read()
                time.sleep(0)
        except EOFError:
            pass
        img = scan_src.get_img(nb_pages)

        try:
            os.makedirs(self.path)
        except OSError:
            pass

        page_nb = self.nb_pages
        page = ImgPage(self, page_nb)
        page.make(img, ocrlang, resolution,
                  scanner_calibration, callback)

    def __get_pages(self):
        """
        Return a list of pages.
        Pages are instantiated on-the-fly.
        """
        return _ImgPageList(self)

    pages = property(__get_pages)

    def print_page_cb(self, print_op, print_context, page_nb):
        """
        Called for printing operation by Gtk
        """
        page = ImgPage(self, page_nb)
        page.print_page_cb(print_op, print_context)

    @staticmethod
    def get_export_formats():
        return []

    def build_exporter(self, file_format='pdf'):
        raise NotImplementedError()



def is_img_doc(filelist):
    for filename in filelist:
        if ".jpg" in filename.lower():
            return True
    return False
