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

import os
import shutil

import gi
from gi.repository import Gio
from gi.repository import Poppler

from paperwork.backend.common.doc import BasicDoc
from paperwork.backend.pdf.page import PdfPage


PDF_FILENAME = "doc.pdf"
PDF_IMPORT_MIN_KEYWORDS = 5


class PdfDocExporter(object):
    can_change_quality = False

    def __init__(self, doc):
        self.pdfpath = ("%s/%s" % (doc.path, PDF_FILENAME))

    def get_mime_type(self):
        return 'application/pdf'

    def get_file_extensions(self):
        return ['pdf']

    def save(self, target_path):
        shutil.copy(self.pdfpath, target_path)
        return target_path

    def set_quality(self, quality):
        raise NotImplementedError()

    def estimate_size(self):
        return os.path.getsize(self.pdfpath)

    def get_img(self):
        raise NotImplementedError()

    def __str__(self):
        return 'PDF'


class PdfDoc(BasicDoc):
    can_edit = False
    doctype = u"PDF"

    def __init__(self, docpath, docid=None):
        BasicDoc.__init__(self, docpath, docid)
        self.pdf = None
        self.pages = []
        if docid != None:
            self._open()

    def _open(self):
        self.pdf = Poppler.Document.new_from_file(
            ("file://%s/%s" % (self.path, PDF_FILENAME)),
             password=None)
        self.pages = [PdfPage(self, page_idx) \
                      for page_idx in range(0, self.pdf.get_n_pages())]

    def __get_nb_pages(self):
        return len(self.pages)

    nb_pages = property(__get_nb_pages)

    def print_page_cb(self, print_op, print_context, page_nb):
        """
        Called for printing operation by Gtk
        """
        self.pages[page_nb].print_page_cb(print_op, print_context)

    def import_pdf(self, config, file_uri):
        print "PDF: Importing '%s'" % (file_uri)
        try:
            dest = Gio.File.parse_name("file://%s" % self.path)
            dest.make_directory(None)
        except gi._glib.GError:
            print ("Warning: Error while trying to create '%s': %s" %
                   (self.path, str(exc)))
        f = Gio.File.parse_name(file_uri)
        dest = dest.get_child(PDF_FILENAME)
        f.copy(dest,
               0,  # TODO(Jflesch): Missing flags: don't keep attributes
               None, None, None)
        self._open()
        nb_keywords = 0
        for keyword in self.keywords:
            nb_keywords += 1
            if nb_keywords >= PDF_IMPORT_MIN_KEYWORDS:
                break
        if nb_keywords < PDF_IMPORT_MIN_KEYWORDS:
            self.redo_ocr(config.ocrlang)

    @staticmethod
    def get_export_formats():
        return ['PDF']

    def build_exporter(self, file_format='pdf'):
        return PdfDocExporter(self)


def is_pdf_doc(docpath):
    try:
        filelist = os.listdir(docpath)
    except OSError, exc:
        print "Warning: Failed to list files in %s: %s" % (docpath, str(exc))
        return False
    return PDF_FILENAME in filelist
