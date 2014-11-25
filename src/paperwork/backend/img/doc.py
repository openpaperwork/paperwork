#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
#    Copyright (C) 2012  Sebastien Maccagnoni-Munch
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
Code for managing documents (not page individually ! see page.py for that)
"""

import errno
import os
import os.path
import logging
import urllib

import cairo
import PIL.Image
from gi.repository import Poppler

from paperwork.backend.common.doc import BasicDoc
from paperwork.backend.img.page import ImgPage
from paperwork.backend.util import image2surface
from paperwork.backend.util import surface2image
from paperwork.backend.util import mkdir_p

logger = logging.getLogger(__name__)


class ImgToPdfDocExporter(object):
    can_change_quality = True
    can_select_format = True
    valid_exts = ['pdf']

    def __init__(self, doc):
        self.doc = doc
        self.__quality = 75
        self.__preview = None  # will just contain the first page
        self.__page_format = (0, 0)

    def get_mime_type(self):
        return 'application/pdf'

    def get_file_extensions(self):
        return ['pdf']

    def __save(self, target_path, pages):
        pdf_surface = cairo.PDFSurface(target_path,
                                       self.__page_format[0],
                                       self.__page_format[1])
        pdf_context = cairo.Context(pdf_surface)

        quality = float(self.__quality) / 100.0

        for page in [self.doc.pages[x] for x in range(pages[0], pages[1])]:
            img = page.img
            if (img.size[0] < img.size[1]):
                (x, y) = (min(self.__page_format[0], self.__page_format[1]),
                          max(self.__page_format[0], self.__page_format[1]))
            else:
                (x, y) = (max(self.__page_format[0], self.__page_format[1]),
                          min(self.__page_format[0], self.__page_format[1]))
            pdf_surface.set_size(x, y)
            new_size = (int(quality * img.size[0]),
                        int(quality * img.size[1]))
            img = img.resize(new_size, PIL.Image.ANTIALIAS)

            scale_factor_x = x / img.size[0]
            scale_factor_y = y / img.size[1]
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

        pdfdoc = Poppler.Document.new_from_file(
            ("file://%s" % urllib.quote(path)), password=None)
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

    def set_page_format(self, page_format):
        self.__page_format = page_format
        self.__preview = None

    def estimate_size(self):
        if self.__preview is None:
            self.refresh()
        return os.path.getsize(self.__preview[0]) * self.doc.nb_pages

    def get_img(self):
        if self.__preview is None:
            self.refresh()
        return self.__preview[1]

    def __str__(self):
        return 'PDF'


class _ImgPagesIterator(object):

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


class _ImgPages(object):

    """
    Page list. Page are accessed using [] operator.
    """

    def __init__(self, doc):
        self.doc = doc

        nb_pages = self.doc.nb_pages
        self.__pages = [ImgPage(doc, idx) for idx in range(0, nb_pages)]

    def add(self, page):
        self.__pages.append(page)
        self.doc.drop_cache()

    def __getitem__(self, idx):
        return self.__pages[idx]

    def __len__(self):
        return self.doc.nb_pages

    def __contains__(self, page):
        return (page.doc == self.doc and page.page_nb <= self.doc.nb_pages)

    def __eq__(self, other):
        return (self.doc == other.doc)

    def __iter__(self):
        return _ImgPagesIterator(self)


class ImgDoc(BasicDoc):

    """
    Represents a document (aka a set of pages + labels).
    """
    IMPORT_IMG_EXTENSIONS = [
        ".jpg",
        ".jpeg",
        ".png"
    ]
    can_edit = True
    doctype = u"Img"

    def __init__(self, docpath, docid=None):
        """
        Arguments:
            docpath --- For an existing document, the path to its folder. For
                a new one, the rootdir of all documents
            docid --- Document Id (ie folder name). Use None for a new document
        """
        BasicDoc.__init__(self, docpath, docid)
        self.__pages = None

    def __get_last_mod(self):
        last_mod = 0.0
        for page in self.pages:
            if last_mod < page.last_mod:
                last_mod = page.last_mod
        labels_path = os.path.join(self.path, BasicDoc.LABEL_FILE)
        try:
            file_last_mod = os.stat(labels_path).st_mtime
            if file_last_mod > last_mod:
                last_mod = file_last_mod
        except OSError:
            pass
        extra_txt_path = os.path.join(self.path, BasicDoc.EXTRA_TEXT_FILE)
        try:
            file_last_mod = os.stat(extra_txt_path).st_mtime
            if file_last_mod > last_mod:
                last_mod = file_last_mod
        except OSError:
            pass
        return last_mod

    last_mod = property(__get_last_mod)

    def __get_pages(self):
        if self.__pages is None:
            self.__pages = _ImgPages(self)
        return self.__pages

    pages = property(__get_pages)

    def _get_nb_pages(self):
        """
        Compute the number of pages in the document. It basically counts
        how many JPG files there are in the document.
        """
        try:
            filelist = os.listdir(self.path)
            count = 0
            for filename in filelist:
                if (filename[-4:].lower() != "." + ImgPage.EXT_IMG
                    or (filename[-10:].lower() == "." + ImgPage.EXT_THUMB)
                    or (filename[:len(ImgPage.FILE_PREFIX)].lower() !=
                        ImgPage.FILE_PREFIX)):
                    continue
                count += 1
            return count
        except OSError, exc:
            if exc.errno != errno.ENOENT:
                logging.error("Exception while trying to get the number of"
                              " pages of '%s': %s" % (self.docid, exc))
                raise
            return 0

    def print_page_cb(self, print_op, print_context, page_nb, keep_refs={}):
        """
        Called for printing operation by Gtk
        """
        page = ImgPage(self, page_nb)
        page.print_page_cb(print_op, print_context, keep_refs=keep_refs)

    @staticmethod
    def get_export_formats():
        return ['PDF']

    def build_exporter(self, file_format='pdf'):
        return ImgToPdfDocExporter(self)

    def steal_page(self, page):
        """
        Steal a page from another document
        """
        if page.doc == self:
            return
        mkdir_p(self.path)

        new_page = ImgPage(self, self.nb_pages)
        logger.info("%s --> %s" % (str(page), str(new_page)))
        new_page._steal_content(page)
        page.doc.drop_cache()
        self.drop_cache()

    def drop_cache(self):
        BasicDoc.drop_cache(self)
        del(self.__pages)
        self.__pages = None

    def get_docfilehash(self):
        if self._get_nb_pages() == 0:
            print "WARNING: Document %s is empty" % self.docid
            dochash = ''
        else:
            dochash = 0
            for page in self.pages:
                dochash ^= page.get_docfilehash()
        return dochash

    def add_page(self, img, boxes):
        mkdir_p(self.path)
        page = ImgPage(self, self.nb_pages)
        page.img = img
        page.boxes = boxes
        self.drop_cache()
        return self.pages[-1]


def is_img_doc(docpath):
    if not os.path.isdir(docpath):
        return False
    try:
        filelist = os.listdir(docpath)
    except OSError, exc:
        logging.warn("Warning: Failed to list files in %s: %s"
                     % (docpath, str(exc)))
        return False
    for filename in filelist:
        if (filename.lower().endswith(ImgPage.EXT_IMG)
                and not filename.lower().endswith(ImgPage.EXT_THUMB)):
            return True
    return False
