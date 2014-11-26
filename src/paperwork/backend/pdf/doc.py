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

import os
import shutil
import logging
import urllib

from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Poppler

from paperwork.backend.common.doc import BasicDoc
from paperwork.backend.pdf.page import PdfPage


PDF_FILENAME = "doc.pdf"
logger = logging.getLogger(__name__)


class PdfDocExporter(object):
    can_select_format = False
    can_change_quality = False

    def __init__(self, doc):
        self.doc = doc
        self.pdfpath = ("%s/%s" % (doc.path, PDF_FILENAME))

    def get_mime_type(self):
        return 'application/pdf'

    def get_file_extensions(self):
        return ['pdf']

    def save(self, target_path):
        shutil.copy(self.pdfpath, target_path)
        return target_path

    def estimate_size(self):
        return os.path.getsize(self.pdfpath)

    def get_img(self):
        return self.doc.pages[0].img

    def __str__(self):
        return 'PDF'


class PdfPagesIterator(object):
    def __init__(self, pdfdoc):
        self.pdfdoc = pdfdoc
        self.idx = 0
        self.pages = [pdfdoc.pages[i] for i in range(0, pdfdoc.nb_pages)]

    def __iter__(self):
        return self

    def next(self):
        if self.idx >= self.pdfdoc.nb_pages:
            raise StopIteration()
        page = self.pages[self.idx]
        self.idx += 1
        return page


class PdfPages(object):
    def __init__(self, pdfdoc):
        self.pdfdoc = pdfdoc
        self.page = {}

    def __getitem__(self, idx):
        if idx < 0:
            idx = self.pdfdoc.nb_pages + idx
        if idx not in self.page:
            self.page[idx] = PdfPage(self.pdfdoc, idx)
        return self.page[idx]

    def __len__(self):
        return self.pdfdoc.nb_pages

    def __iter__(self):
        return PdfPagesIterator(self.pdfdoc)


class PdfDoc(BasicDoc):
    can_edit = False
    doctype = u"PDF"

    def __init__(self, docpath, docid=None):
        BasicDoc.__init__(self, docpath, docid)
        self.__pdf = None
        self.__nb_pages = 0
        self.__pages = None

    def __get_last_mod(self):
        pdfpath = os.path.join(self.path, PDF_FILENAME)
        last_mod = os.stat(pdfpath).st_mtime
        for page in self.pages:
            if page.last_mod > last_mod:
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

    def get_pdf_file_path(self):
        return ("%s/%s" % (self.path, PDF_FILENAME))

    def _open_pdf(self):
        self.__pdf = Poppler.Document.new_from_file(
            ("file://%s/%s" % (urllib.quote(self.path), PDF_FILENAME)),
            password=None)
        self.__nb_pages = self.pdf.get_n_pages()
        self.__pages = PdfPages(self)

    def __get_pdf(self):
        if self.__pdf is None:
            self._open_pdf()
        return self.__pdf

    pdf = property(__get_pdf)

    def __get_pages(self):
        if self.__pdf is None:
            self._open_pdf()
        return self.__pages

    pages = property(__get_pages)

    def _get_nb_pages(self):
        if self.__pdf is None:
            if self.is_new:
                # happens when a doc was recently deleted
                return 0
            self._open_pdf()
        return self.__nb_pages

    def print_page_cb(self, print_op, print_context, page_nb, keep_refs={}):
        """
        Called for printing operation by Gtk
        """
        self.pages[page_nb].print_page_cb(print_op, print_context,
                                          keep_refs=keep_refs)

    def import_pdf(self, config, file_uri):
        logger.info("PDF: Importing '%s'" % (file_uri))
        try:
            dest = Gio.File.parse_name("file://%s" % urllib.quote(self.path))
            dest.make_directory(None)
        except GLib.GError, exc:
            logger.exception("Warning: Error while trying to create '%s': %s"
                             % (self.path, exc))
        f = Gio.File.parse_name(file_uri)
        dest = dest.get_child(PDF_FILENAME)
        f.copy(dest,
               0,  # TODO(Jflesch): Missing flags: don't keep attributes
               None, None, None)
        self._open_pdf()

    @staticmethod
    def get_export_formats():
        return ['PDF']

    def build_exporter(self, file_format='pdf'):
        return PdfDocExporter(self)

    def drop_cache(self):
        BasicDoc.drop_cache(self)
        del(self.__pdf)
        self.__pdf = None
        del(self.__pages)
        self.__pages = None

    def get_docfilehash(self):
        return BasicDoc.hash_file("%s/%s" % (self.path, PDF_FILENAME))


def is_pdf_doc(docpath):
    if not os.path.isdir(docpath):
        return False
    try:
        filelist = os.listdir(docpath)
    except OSError, exc:
        logger.exception("Warning: Failed to list files in %s: %s"
                         % (docpath, str(exc)))
        return False
    return PDF_FILENAME in filelist
