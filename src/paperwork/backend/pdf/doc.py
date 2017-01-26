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

import logging
import os
import shutil

from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Poppler

from ..common.doc import BasicDoc
from ..common.doc import dummy_export_progress_cb
from ..pdf.page import PdfPage

PDF_FILENAME = "doc.pdf"
logger = logging.getLogger(__name__)


class PdfDocExporter(object):
    can_select_format = False
    can_change_quality = False

    def __init__(self, doc, page_nb):
        self.doc = doc
        self.page = doc.pages[page_nb]
        self.pdfpath = ("%s/%s" % (doc.path, PDF_FILENAME))

    def get_mime_type(self):
        return 'application/pdf'

    def get_file_extensions(self):
        return ['pdf']

    def save(self, target_path, progress_cb=dummy_export_progress_cb):
        progress_cb(0, 1)
        shutil.copy(self.pdfpath, target_path)
        progress_cb(1, 1)
        return target_path

    def estimate_size(self):
        return os.path.getsize(self.pdfpath)

    def get_img(self):
        return self.page.img

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

    def __next__(self):
        return self.next()


class PdfPages(object):
    def __init__(self, pdfdoc, pdf):
        self.pdfdoc = pdfdoc
        self.pdf = pdf
        self.page = {}

    def __getitem__(self, idx):
        if idx < 0:
            idx = self.pdf.get_n_pages() + idx
        if idx not in self.page:
            self.page[idx] = PdfPage(self.pdfdoc, self.pdf, idx)
        return self.page[idx]

    def __len__(self):
        return self.pdf.get_n_pages()

    def __iter__(self):
        return PdfPagesIterator(self.pdfdoc)

    def __del__(self):
        for page in self.page.values():
            del page


NB_FDS = 0  # assumed number of file descriptors opened


class PdfDoc(BasicDoc):
    can_edit = False
    doctype = u"PDF"

    def __init__(self, docpath, docid=None):
        BasicDoc.__init__(self, docpath, docid)
        self._pages = None
        self._pdf = None

    def clone(self):
        return PdfDoc(self.path, self.docid)

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
        global NB_FDS
        if self._pdf:
            return self._pdf
        dirpath = Gio.File.new_for_path(self.path)
        file = dirpath.resolve_relative_path(PDF_FILENAME)
        self._pdf = Poppler.Document.new_from_gfile(file, password=None)
        NB_FDS += 1
        logger.debug("(opening {}) Number of PDF file descriptors"
                     " opened: {}".format(self, NB_FDS))
        return self._pdf

    pdf = property(_open_pdf)

    def __get_pages(self):
        if self._pages:
            return self._pages
        self._pages = PdfPages(self, self.pdf)
        return self._pages

    pages = property(__get_pages)

    def _get_nb_pages(self):
        if self.is_new:
            # happens when a doc was recently deleted
            return 0
        nb_pages = self.pdf.get_n_pages()
        return nb_pages

    def print_page_cb(self, print_op, print_context, page_nb, keep_refs={}):
        """
        Called for printing operation by Gtk
        """
        self.pages[page_nb].print_page_cb(print_op, print_context,
                                          keep_refs=keep_refs)

    def import_pdf(self, file_uri):
        logger.info("PDF: Importing '%s'" % (file_uri))
        try:
            # try opening it to make sure it's valid
            pdf = Poppler.Document.new_from_file(file_uri)
            pdf.get_n_pages()
        except GLib.GError as exc:
            logger.error(
                "Warning: Unable to open the PDF to import: {}/{}".format(
                    file_uri, exc
                )
            )
            return str(exc)

        try:
            dest = Gio.File.new_for_path(self.path)
            dest.make_directory(None)
        except GLib.GError as exc:
            logger.error("Warning: Error while trying to create '%s': %s"
                         % (self.path, exc))
            return str(exc)
        f = Gio.File.parse_name(file_uri)
        dest = dest.get_child(PDF_FILENAME)
        f.copy(dest,
               0,  # TODO(Jflesch): Missing flags: don't keep attributes
               None, None, None)
        return None

    @staticmethod
    def get_export_formats():
        return ['PDF']

    def build_exporter(self, file_format='pdf', preview_page_nb=0):
        assert(file_format.lower() == 'pdf')
        return PdfDocExporter(self, preview_page_nb)

    def drop_cache(self):
        global NB_FDS
        BasicDoc.drop_cache(self)
        if self._pages:
            del self._pages
        self._pages = None
        if self._pdf:
            NB_FDS -= 1
            del self._pdf
            logger.debug("(closing {}) Number of PDF file descriptors"
                         " still opened: {}".format(self, NB_FDS))
        self._pdf = None

    def get_docfilehash(self):
        return BasicDoc.hash_file("%s/%s" % (self.path, PDF_FILENAME))


def is_pdf_doc(docpath):
    if not os.path.isdir(docpath):
        return False
    try:
        filelist = os.listdir(docpath)
    except OSError as exc:
        logger.exception("Warning: Failed to list files in %s: %s"
                         % (docpath, str(exc)))
        return False
    return PDF_FILENAME in filelist
