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

"""
Document import (PDF, images, etc)
"""

import gettext
import logging
import urllib

from gi.repository import GLib
from gi.repository import Gio
from PIL import Image

from .pdf.doc import PdfDoc
from .img.doc import ImgDoc

_ = gettext.gettext
logger = logging.getLogger(__name__)


class SinglePdfImporter(object):

    """
    Import a single PDF file as a document
    """

    def __init__(self):
        pass

    @staticmethod
    def can_import(file_uri, current_doc=None):
        """
        Check that the specified file looks like a PDF
        """
        return file_uri.lower().endswith(".pdf")

    @staticmethod
    def import_doc(file_uri, docsearch, current_doc=None):
        """
        Import the specified PDF file
        """
        doc = PdfDoc(docsearch.rootdir)
        logger.info("Importing doc '%s' ..." % file_uri)
        error = doc.import_pdf(file_uri)
        if error:
            raise Exception("Import of {} failed: {}".format(file_uri, error))
        return ([doc], None, True)

    def __str__(self):
        return _("Import PDF")


class MultiplePdfImporter(object):

    """
    Import many PDF files as many documents
    """

    def __init__(self):
        pass

    @staticmethod
    def __get_all_children(parent):
        """
        Find all the children files from parent
        """
        children = parent.enumerate_children(
            Gio.FILE_ATTRIBUTE_STANDARD_NAME,
            Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
            None)
        for child in children:
            name = child.get_name()
            child = parent.get_child(name)
            try:
                for child in MultiplePdfImporter.__get_all_children(child):
                    yield child
            except GLib.GError:
                yield child

    @staticmethod
    def can_import(file_uri, current_doc=None):
        """
        Check that the specified file looks like a directory containing many
        pdf files
        """
        try:
            parent = Gio.File.parse_name(file_uri)
            for child in MultiplePdfImporter.__get_all_children(parent):
                if child.get_basename().lower().endswith(".pdf"):
                    return True
        except GLib.GError:
            pass
        return False

    @staticmethod
    def import_doc(file_uri, docsearch, current_doc=None):
        """
        Import the specified PDF files
        """
        logger.info("Importing PDF from '%s'" % (file_uri))
        parent = Gio.File.parse_name(file_uri)
        doc = None
        docs = []

        idx = 0

        for child in MultiplePdfImporter.__get_all_children(parent):
            if not child.get_basename().lower().endswith(".pdf"):
                continue
            if docsearch.is_hash_in_index(PdfDoc.hash_file(child.get_path())):
                logger.info("Document %s already found in the index. Skipped"
                            % (child.get_path()))
                continue
            doc = PdfDoc(docsearch.rootdir)
            error = doc.import_pdf(child.get_uri())
            if error:
                continue
            docs.append(doc)
            idx += 1
        if doc is None:
            return (None, None, False)
        else:
            return (docs, None, True)

    def __str__(self):
        return _("Import each PDF in the folder as a new document")


class SingleImageImporter(object):

    """
    Import a single image file (in a format supported by PIL). It is either
    added to a document (if one is specified) or as a new document (--> with a
    single page)
    """

    def __init__(self):
        pass

    @staticmethod
    def can_import(file_uri, current_doc=None):
        """
        Check that the specified file looks like an image supported by PIL
        """
        for ext in ImgDoc.IMPORT_IMG_EXTENSIONS:
            if file_uri.lower().endswith(ext):
                return True
        return False

    @staticmethod
    def import_doc(file_uri, docsearch, current_doc=None):
        """
        Import the specified image
        """
        logger.info("Importing doc '%s'" % (file_uri))
        if current_doc is None:
            current_doc = ImgDoc(docsearch.rootdir)
        new = current_doc.is_new
        if file_uri[:7] == "file://":
            # XXX(Jflesch): bad bad bad
            file_uri = urllib.parse.unquote(file_uri[7:])
        img = Image.open(file_uri)
        page = current_doc.add_page(img, [])
        return ([current_doc], page, new)

    def __str__(self):
        return _("Append the image to the current document")


IMPORTERS = [
    SinglePdfImporter(),
    SingleImageImporter(),
    MultiplePdfImporter(),
]


def get_possible_importers(file_uri, current_doc=None):
    """
    Return all the importer objects that can handle the specified file.

    Possible imports may vary depending on the currently active document
    """
    importers = []
    for importer in IMPORTERS:
        if importer.can_import(file_uri, current_doc):
            importers.append(importer)
    return importers
