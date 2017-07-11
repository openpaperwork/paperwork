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

from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Poppler

from ..common.doc import BasicDoc
from ..common.export import Exporter
from ..common.export import dummy_export_progress_cb
from ..pdf.page import PdfPage

PDF_FILENAME = "doc.pdf"
logger = logging.getLogger(__name__)


class PdfDocExporter(Exporter):
    def __init__(self, doc, page_nb):
        super().__init__(doc, 'PDF')
        self.can_select_format = False
        self.can_change_quality = False
        self.doc = doc
        self.page = doc.pages[page_nb]
        self.pdfpath = doc.fs.join(doc.path, PDF_FILENAME)

    def get_mime_type(self):
        return 'application/pdf'

    def get_file_extensions(self):
        return ['pdf']

    def save(self, target_path, progress_cb=dummy_export_progress_cb):
        target_path = self.doc.fs.safe(target_path)
        progress_cb(0, 1)
        self.doc.fs.copy(self.pdfpath, target_path)
        progress_cb(1, 1)
        return target_path

    def estimate_size(self):
        return self.doc.fs.getsize(self.pdfpath)

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
    def __init__(self, pdfdoc, on_disk_cache=False):
        self.pdfdoc = pdfdoc
        self.on_disk_cache = on_disk_cache

    def __getitem__(self, idx):
        if idx < 0:
            idx = self.pdf.get_n_pages() + idx
        return PdfPage(self.pdfdoc, idx,
                       self.on_disk_cache)

    def __len__(self):
        return self.pdf.get_n_pages()

    def __iter__(self):
        return PdfPagesIterator(self.pdfdoc)


class _CommonPdfDoc(BasicDoc):
    can_edit = False
    doctype = u"PDF"

    def __init__(self, fs, pdfpath, docpath, docid=None, on_disk_cache=False):
        super().__init__(fs, docpath, docid)
        self.pdfpath = fs.safe(pdfpath)
        self._on_disk_cache = on_disk_cache
        # number of pages never change --> we can keep it in memory safely
        self._nb_pages = -1

    def clone(self):
        assert()

    def _get_last_mod(self):
        last_mod = self.fs.getmtime(self.pdfpath)
        for page in self.pages:
            if page.last_mod > last_mod:
                last_mod = page.last_mod
        return last_mod

    last_mod = property(_get_last_mod)

    def get_pdf_file_path(self):
        return self.pdfpath

    def get_pdf(self):
        logger.info("PDF: Opening {}".format(self.pdfpath))
        filepath = Gio.File.new_for_uri(self.pdfpath)
        return Poppler.Document.new_from_gfile(filepath, password=None)

    def __get_pages(self):
        return PdfPages(self, self._on_disk_cache)

    pages = property(__get_pages)

    def _get_nb_pages(self):
        if self._nb_pages >= 0:
            return self._nb_pages
        if self.is_new:
            # happens when a doc was recently deleted
            return 0
        self._nb_pages = self.get_pdf().get_n_pages()
        return self._nb_pages

    def print_page_cb(self, print_op, print_context, page_nb, keep_refs={}):
        """
        Called for printing operation by Gtk
        """
        self.pages[page_nb].print_page_cb(print_op, print_context,
                                          keep_refs=keep_refs)

    def import_pdf(self, file_uri):
        assert()

    @staticmethod
    def get_export_formats():
        return ['PDF']

    def build_exporter(self, file_format='pdf', preview_page_nb=0):
        assert(file_format.lower() == 'pdf')
        return PdfDocExporter(self, preview_page_nb)

    def get_docfilehash(self):
        return super().hash_file(self.fs, "%s/%s" % (self.path, PDF_FILENAME))


class PdfDoc(_CommonPdfDoc):
    """
    PDF document inside the work directory
    (by opposition to OutsidePdfDoc that can be located anywhere)
    """
    can_edit = False
    doctype = u"PDF"

    def __init__(self, fs, docpath, docid=None):
        super().__init__(
            fs,
            fs.join(docpath, PDF_FILENAME),
            docpath, docid,
            on_disk_cache=True
        )

    def clone(self):
        return PdfDoc(self.fs, self.path, self.docid)

    def _get_last_mod(self):
        last_mod = super()._get_last_mod()
        labels_path = self.fs.join(self.path, self.LABEL_FILE)
        try:
            file_last_mod = self.fs.getmtime(labels_path)
            if file_last_mod > last_mod:
                last_mod = file_last_mod
        except OSError:
            pass
        extra_txt_path = self.fs.join(self.path, self.EXTRA_TEXT_FILE)
        try:
            file_last_mod = self.fs.getmtime(extra_txt_path)
            if file_last_mod > last_mod:
                last_mod = file_last_mod
        except OSError:
            pass
        return last_mod

    last_mod = property(_get_last_mod)

    def import_pdf(self, file_uri):
        logger.info("PDF: Importing '%s'" % (file_uri))
        gfile = Gio.File.new_for_uri(file_uri)
        try:
            # try opening it to make sure it's valid
            pdf = Poppler.Document.new_from_gfile(gfile)
            pdf.get_n_pages()
        except GLib.GError as exc:
            logger.error(
                "Warning: Unable to open the PDF to import: {}/{}".format(
                    file_uri, exc
                )
            )
            return str(exc)

        try:
            dest = Gio.File.new_for_uri(self.path)
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
        self.pdfpath = dest.get_uri()
        return None


class ExternalPdfDoc(_CommonPdfDoc):
    """
    PDF document outside of the work directory.
    For instance, it can be a help document describing how to use the software.
    --> You do not want to add this document to the work directory
    --> You do not want to create thumbnail files, etc
    --> You do not want a label file
    """
    can_edit = False
    doctype = "PDF"
    labels = []
    is_new = False
    extra_text = ""
    has_ocr = False

    def __init__(self, fs, filepath):
        super().__init__(
            fs,
            filepath,
            fs.dirname(filepath), fs.basename(filepath),
            on_disk_cache=False
        )
        self.filepath = filepath

    # disable all the methods to handle the document

    def clone(self):
        assert()

    def destroy(self):
        assert()

    def add_label(self, *args, **kwargs):
        assert()

    def remove_label(self, *args, **kwargs):
        assert()

    def update_label(self, *args, **kwargs):
        assert()

    def _set_docid(self, *args, **kwargs):
        assert()


def is_pdf_doc(fs, docpath):
    if not fs.isdir(docpath):
        return False
    try:
        filelist = fs.listdir(docpath)
        filelist = [fs.basename(filepath) for filepath in filelist]
    except OSError as exc:
        logger.exception("Warning: Failed to list files in %s: %s"
                         % (docpath, str(exc)))
        return False
    return PDF_FILENAME in filelist
