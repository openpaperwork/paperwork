import gettext
import gio
import poppler

from paperwork.model.pdf.doc import PdfDoc

_ = gettext.gettext


class SinglePdfImporter(object):
    def __init__(self):
        pass

    def can_import(self, file_uri, current_doc=None):
        return file_uri.lower().endswith(".pdf")

    def import_doc(self, file_uri, config, docsearch, current_doc=None):
        doc = PdfDoc(config.workdir)
        doc.import_pdf(config, file_uri)
        for page in doc.pages:
            docsearch.index_page(page)
        return doc

    def __str__(self):
        return _("Import PDF")


class MultiplePdfImporter(object):
    def __init__(self):
        pass

    def __get_all_children(self, parent):
        children = parent.enumerate_children(
                attributes=gio.FILE_ATTRIBUTE_STANDARD_NAME,
                flags=gio.FILE_QUERY_INFO_NOFOLLOW_SYMLINKS)
        for child in children:
            name = child.get_attribute_as_string(
                    gio.FILE_ATTRIBUTE_STANDARD_NAME)
            child = parent.get_child(name)
            try:
                for child in self.__get_all_children(child):
                    yield child
            except gio.Error:
                yield child

    def can_import(self, file_uri, current_doc=None):
        try:
            parent = gio.File(file_uri)
            for child in self.__get_all_children(parent):
                if child.get_basename().lower().endswith(".pdf"):
                    return True
        except gio.Error:
            pass
        return False

    def import_doc(self, file_uri, config, docsearch, current_doc=None):
        parent = gio.File(file_uri)
        doc = None

        idx = 0

        for child in self.__get_all_children(parent):
            if not child.get_basename().lower().endswith(".pdf"):
                continue
            try:
                # make sure we can import it
                poppler.document_new_from_file(child.get_uri(),
                                               password=None)
            except Exception:
                continue
            doc = PdfDoc(config.workdir)
            doc.path += ("_%02d" % idx)
            doc.docid += ("_%02d" % idx)
            doc.import_pdf(config, child.get_uri())
            for page in doc.pages:
                docsearch.index_page(page)
            idx += 1

        assert(doc != None)
        return doc

    def __str__(self):
        return _("Import each PDF in the folder as a new document")


IMPORTERS = [
    SinglePdfImporter(),
    MultiplePdfImporter(),
]

def get_possible_importers(file_uri, current_doc=None):
    importers = []
    for importer in IMPORTERS:
        if importer.can_import(file_uri, current_doc):
            importers.append(importer)
    return importers
