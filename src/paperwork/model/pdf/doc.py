import gio
import poppler

from paperwork.model.common.doc import BasicDoc
from paperwork.model.pdf.page import PdfPage


PDF_FILENAME = "doc.pdf"
PDF_IMPORT_MIN_KEYWORDS = 5

class PdfDoc(BasicDoc):
    can_edit = False

    def __init__(self, docpath, docid=None):
        BasicDoc.__init__(self, docpath, docid)
        self.pdf = None
        self.pages = []
        if docid != None:
            self._open()

    def _open(self):
        self.pdf = poppler.document_new_from_file(
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
            dest = gio.File("file://%s" % self.path)
            dest.make_directory()
        except gio.Error, exc:
            print ("Warning: Error while trying to create '%s': %s" %
                   (self.path, str(exc)))
        f = gio.File(file_uri)
        dest = dest.get_child(PDF_FILENAME)
        f.copy(dest)
        self._open()
        nb_keywords = 0
        for keyword in self.keywords:
            nb_keywords += 1
            if nb_keywords >= PDF_IMPORT_MIN_KEYWORDS:
                break
        if nb_keywords < PDF_IMPORT_MIN_KEYWORDS:
            self.redo_ocr(config.ocrlang)


def is_pdf_doc(filelist):
    return PDF_FILENAME in filelist

