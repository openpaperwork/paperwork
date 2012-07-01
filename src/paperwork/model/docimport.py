import gettext
import poppler

from paperwork.model.pdf.doc import PdfDoc

_ = gettext.gettext

class PdfImporter(object):
    def __init__(self):
        pass

    def can_import(self, file_uri, current_doc=None):
        try:
            print "PDF Importer: Will try to open '%s'" % (file_uri)
            poppler.document_new_from_file(file_uri, password="cowabunga")
            return True
        except Exception:
            return False

    def import_doc(self, file_uri, config, docsearch, current_doc=None):
        doc = PdfDoc(config.workdir)
        doc.import_pdf(file_uri)
        for page in doc.pages:
            docsearch.index_page(page)
        return doc

    def __str__(self):
        return _("Import PDF")


IMPORTERS = [
    PdfImporter()
]

def get_possible_importers(file_uri, current_doc=None):
    importers = []
    for importer in IMPORTERS:
        if importer.can_import(file_uri, current_doc):
            importers.append(importer)
    return importers
