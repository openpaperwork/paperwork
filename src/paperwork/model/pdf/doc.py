import poppler

from paperwork.model.common.doc import BasicDoc
from paperwork.model.pdf.page import PdfPage


PDF_FILENAME = "doc.pdf"


class PdfDoc(BasicDoc):
    def __init__(self, docpath, docid=None):
        BasicDoc.__init__(self, docpath, docid)
        self.pdf = poppler.document_new_from_file(
            ("file://%s/%s" % (docpath, PDF_FILENAME)),
             password="cowabunga")
        self.pages = [PdfPage(self, page_idx) \
                      for page_idx in range(0, self.nb_pages)]

    def __get_nb_pages(self):
        return self.pdf.get_n_pages()

    nb_pages = property(__get_nb_pages)


def is_pdf_doc(filelist):
    return PDF_FILENAME in filelist

