"""
Code for managing documents (not page individually ! see page.py for that)
"""

import codecs
import datetime
import os
import os.path
import time

import cairo
import Image
import poppler

from paperwork.model.common.doc import BasicDoc
from paperwork.model.img.page import ImgPage
from paperwork.util import dummy_progress_cb
from paperwork.util import surface2image
from paperwork.util import image2surface


class ImgToPdfDocExporter(object):
    can_change_quality = True
    valid_exts = ['pdf']
    PDF_A4_FORMAT = (595, 842)

    def __init__(self, doc):
        self.doc = doc
        self.__quality = 75
        self.__preview = None  # will just contain the first page

    def get_mime_type(self):
        return 'application/pdf'

    def get_file_extensions(self):
        return ['pdf']

    def __save(self, target_path, pages):
        # TODO(Jflesch): Other formats (Letter, etc)
        pdf_format = self.PDF_A4_FORMAT
        pdf_surface = cairo.PDFSurface(target_path,
                                       pdf_format[0], pdf_format[1])
        pdf_context = cairo.Context(pdf_surface)

        quality = float(self.__quality) / 100.0

        for page in [self.doc.pages[x] for x in range(pages[0], pages[1])]:
            img = page.img
            if (img.size[0] > img.size[1]):
                img = img.rotate(90)
            new_size = (int(quality * img.size[0]),
                        int(quality * img.size[1]))
            img = img.resize(new_size)

            scale_factor_x = float(pdf_format[0]) / img.size[0]
            scale_factor_y = float(pdf_format[1]) / img.size[0]
            scale_factor = min(scale_factor_x, scale_factor_y)

            img_surface = image2surface(img)

            pdf_context.identity_matrix()
            pdf_context.scale(scale_factor, scale_factor)
            pdf_context.set_source_surface(img_surface)
            pdf_context.paint()

            pdf_context.show_page()

        return target_path

    def save(self, target_path):
        return self.__save(target_path, (0, self.doc.nb_pages))

    def refresh(self):
        # make the preview

        tmp = "%s.%s" % (os.tempnam(None, "paperwork_export_"),
                         self.valid_exts[0])
        path = self.__save(tmp, pages=(0, 1))

        # reload the preview

        pdfdoc = poppler.document_new_from_file(
            ("file://%s" % path), password=None)
        assert(pdfdoc.get_n_pages() > 0)

        pdfpage = pdfdoc.get_page(0)
        pdfpage_size = pdfpage.get_size()

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                     int(pdfpage_size[0]),
                                     int(pdfpage_size[1]))
        ctx = cairo.Context(surface)
        pdfpage.render(ctx)
        img = surface2image(surface)

        self.__preview = (path, img)

    def set_quality(self, quality):
        self.__quality = quality
        self.__preview = None

    def estimate_size(self):
        if self.__preview == None:
            self.refresh()
        return os.path.getsize(self.__preview[0]) * self.doc.nb_pages

    def get_img(self):
        if self.__preview == None:
            self.refresh()
        return self.__preview[1]

    def __str__(self):
        return 'PDF'


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
        return ['PDF']

    def build_exporter(self, file_format='pdf'):
        return ImgToPdfDocExporter(self)


def is_img_doc(filelist):
    for filename in filelist:
        if ".jpg" in filename.lower():
            return True
    return False
