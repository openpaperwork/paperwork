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

from gi.repository import GLib
from gi.repository import Gio
from natsort import natsorted
from PIL import Image

from .pdf.doc import PdfDoc
from .img.doc import ImgDoc
from . import fs

_ = gettext.gettext
logger = logging.getLogger(__name__)

IMG_MIME_TYPES = [
    ("BMP", "image/x-ms-bmp"),
    ("GIF", "image/gif"),
    ("JPEG", "image/jpeg"),
    ("PNG", "image/png"),
    ("TIFF", "image/tiff"),
]


class ImportResult(object):
    BASE_STATS = {
        _("PDF"): 0,
        _("Document(s)"): 0,
        _("Image file(s)"): 0,
        _("Page(s)"): 0,
    }

    def __init__(self,
                 imported_file_uris=[],
                 select_doc=None, select_page=None,
                 new_docs=[], upd_docs=[],
                 new_docs_pages=[], upd_docs_pages=[],
                 stats={}):
        if select_doc is None and select_page is not None:
            select_doc = select_page.doc

        if select_doc is not None and select_page is None:
            if select_doc.nb_pages > 0:
                select_page = select_doc.pages[0]

        self.imported_file_uris = imported_file_uris
        self.select_doc = select_doc
        self.select_page = select_page
        self.new_docs = new_docs
        self.upd_docs = upd_docs
        self.new_docs_pages = new_docs_pages
        self.upd_docs_pages = upd_docs_pages
        self.stats = self.BASE_STATS.copy()
        self.stats.update(stats)

    def get(self):
        return {
            "imported_file_uris": self.imported_file_uris,
            "new_docs": [
                {
                    "docid": doc.docid,
                    "labels": [l.name for l in doc.labels],
                }
                for doc in self.new_docs
            ],
            "upd_docs": [
                {
                    "docid": doc.docid,
                    "labels": [l.name for l in doc.labels],
                }
                for doc in self.upd_docs
            ],
            "new_docs_pages": [
                page.pageid for page in self.new_docs_pages
            ],
            "upd_docs_pages": [
                page.pageid for page in self.upd_docs_pages
            ],
            "stats": self.stats,
        }

    @property
    def has_import(self):
        return len(self.new_docs) > 0 or len(self.upd_docs) > 0


def recurse(parent):
    children = parent.enumerate_children(
        Gio.FILE_ATTRIBUTE_STANDARD_NAME,
        Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
        None
    )
    for child in children:
        name = child.get_name()
        child = parent.get_child(name)
        try:
            for child in recurse(child):
                yield child
        except GLib.GError:
            yield child


class BaseImporter(object):
    def __init__(self, fs, file_extensions):
        self.fs = fs
        self.file_extensions = file_extensions

    @staticmethod
    def can_import(file_uris, current_doc=None):
        assert()

    @staticmethod
    def import_doc(file_uris, docsearch, current_doc=None):
        assert()

    @staticmethod
    def get_select_mime_types():
        return []

    @staticmethod
    def get_mime_types():
        return []

    def check_file_type(self, file_uri):
        lfile_uri = file_uri.lower()
        for extension in self.file_extensions:
            if lfile_uri.endswith(extension):
                return True
        gfile = Gio.File.new_for_uri(file_uri)
        info = gfile.query_info(
            "standard::content-type", Gio.FileQueryInfoFlags.NONE
        )
        mime = info.get_content_type()
        return mime in [m[1] for m in self.get_mime_types()]


class PdfImporter(BaseImporter):
    """
    Import a single PDF file as a document
    """

    def __init__(self, fs):
        super().__init__(fs, [".pdf"])

    def can_import(self, file_uris, current_doc=None):
        """
        Check that the specified file looks like a PDF
        """
        if len(file_uris) <= 0:
            return False
        for uri in file_uris:
            uri = self.fs.safe(uri)
            if not self.check_file_type(uri):
                return False
        return True

    def import_doc(self, file_uris, docsearch, current_doc=None):
        """
        Import the specified PDF file
        """
        doc = None
        docs = []
        pages = []

        file_uris = [self.fs.safe(uri) for uri in file_uris]
        imported = []
        for file_uri in file_uris:
            if docsearch.is_hash_in_index(PdfDoc.hash_file(self.fs, file_uri)):
                logger.info("Document %s already found in the index. Skipped"
                            % (file_uri))
                continue

            doc = PdfDoc(self.fs, docsearch.rootdir)
            logger.info("Importing doc '%s' ..." % file_uri)
            error = doc.import_pdf(file_uri)
            if error:
                raise Exception("Import of {} failed: {}".format(
                    file_uri, error
                ))
            imported.append(file_uri)
            docs.append(doc)
            pages += [p for p in doc.pages]

        return ImportResult(
            imported_file_uris=imported,
            select_doc=doc, new_docs=docs,
            new_docs_pages=pages,
            stats={
                _("PDF"): len(imported),
                _("Document(s)"): len(imported),
                _("Page(s)"): len(pages),
            }
        )

    @staticmethod
    def get_select_mime_types():
        return [
            ("PDF", "application/pdf"),
        ]

    @staticmethod
    def get_mime_types():
        return [
            ("PDF", "application/pdf"),
        ]

    def __str__(self):
        return _("Import PDF")


class PdfDirectoryImporter(BaseImporter):
    """
    Import many PDF files as many documents
    """

    def __init__(self, fs):
        super().__init__(fs, [".pdf"])

    def can_import(self, file_uris, current_doc=None):
        """
        Check that the specified file looks like a directory containing many
        pdf files
        """
        if len(file_uris) <= 0:
            return False
        try:
            for file_uri in file_uris:
                file_uri = self.fs.safe(file_uri)
                parent = Gio.File.parse_name(file_uri)
                for child in recurse(parent):
                    if self.check_file_type(child.get_uri()):
                        return True
        except GLib.GError:
            pass
        return False

    def import_doc(self, file_uris, docsearch, current_doc=None):
        """
        Import the specified PDF files
        """

        doc = None
        docs = []
        pages = []

        file_uris = [self.fs.safe(uri) for uri in file_uris]
        imported = []
        for file_uri in file_uris:
            logger.info("Importing PDF from '%s'" % (file_uri))
            parent = Gio.File.parse_name(file_uri)
            idx = 0

            for child in recurse(parent):
                if not self.check_file_type(child.get_uri()):
                    continue
                h = PdfDoc.hash_file(self.fs, child.get_uri())
                if docsearch.is_hash_in_index(h):
                    logger.info(
                        "Document %s already found in the index. Skipped",
                        (child.get_path())
                    )
                    continue
                imported.append(child.get_uri())
                doc = PdfDoc(self.fs, docsearch.rootdir)
                error = doc.import_pdf(child.get_uri())
                if error:
                    continue
                docs.append(doc)
                pages += [p for p in doc.pages]
                idx += 1
        return ImportResult(
            imported_file_uris=imported,
            select_doc=doc, new_docs=docs,
            new_docs_pages=pages,
            stats={
                _("PDF"): len(docs),
                _("Document(s)"): len(docs),
                _("Page(s)"): sum([d.nb_pages for d in docs]),
            },
        )

    @staticmethod
    def get_select_mime_types():
        return [
            (_("PDF folder"), "inode/directory"),
        ]

    @staticmethod
    def get_mime_types():
        return [
            ("PDF", "application/pdf"),
        ]

    def __str__(self):
        return _("Import each PDF in the folder as a new document")


class ImageDirectoryImporter(BaseImporter):
    """
    Import many PDF files as many documents
    """

    def __init__(self, fs):
        super().__init__(fs, ImgDoc.IMPORT_IMG_EXTENSIONS)

    def can_import(self, file_uris, current_doc=None):
        """
        Check that the specified file looks like a directory containing many
        pdf files
        """
        if len(file_uris) <= 0:
            return False
        try:
            for file_uri in file_uris:
                file_uri = self.fs.safe(file_uri)
                parent = Gio.File.parse_name(file_uri)
                for child in recurse(parent):
                    if self.check_file_type(child.get_uri()):
                        return True
        except GLib.GError:
            pass
        return False

    def import_doc(self, file_uris, docsearch, current_doc=None):
        """
        Import the specified PDF files
        """
        if (current_doc is None or
                current_doc.is_new or
                not current_doc.can_edit):
            if not current_doc or not current_doc.can_edit:
                current_doc = ImgDoc(self.fs, docsearch.rootdir)
            new_docs = [current_doc]
            upd_docs = []
        else:
            new_docs = []
            upd_docs = [current_doc]
        new_docs_pages = []
        upd_docs_pages = []
        page = None

        file_uris = natsorted(file_uris)
        imported = []

        for file_uri in file_uris:
            file_uri = self.fs.safe(file_uri)
            logger.info("Importing images from '%s'" % (file_uri))
            parent = Gio.File.parse_name(file_uri)

            for child in recurse(parent):
                if ".thumb." in child.get_uri():
                    # We are re-importing an old document --> ignore thumbnails
                    logger.info("{} ignored".format(child.get_uri()))
                    continue
                if not self.check_file_type(child.get_uri()):
                    continue
                imported.append(child.get_uri())
                with self.fs.open(child.get_uri(), "rb") as fd:
                    img = Image.open(fd)
                    img.load()
                page = current_doc.add_page(img, [])
                if new_docs == []:
                    upd_docs_pages.append(page)
                else:
                    new_docs_pages.append(page)

        return ImportResult(
            imported_file_uris=imported,
            select_doc=current_doc, select_page=page,
            new_docs=new_docs, upd_docs=upd_docs,
            new_docs_pages=new_docs_pages,
            upd_docs_pages=upd_docs_pages,
            stats={
                _("Image file(s)"): len(file_uris),
                _("Document(s)"): 0 if new_docs == [] else 1,
                _("Page(s)"): len(new_docs_pages) + len(upd_docs_pages),
            }
        )

    @staticmethod
    def get_mime_types():
        return IMG_MIME_TYPES

    @staticmethod
    def get_select_mime_types():
        return [
            (_("Image folder"), "inode/directory"),
        ]

    def __str__(self):
        return _("Import all image files in the folder in the current document")


class ImageImporter(BaseImporter):
    """
    Import a single image file (in a format supported by PIL). It is either
    added to a document (if one is specified) or as a new document (--> with a
    single page)
    """

    def __init__(self, fs):
        super().__init__(fs, ImgDoc.IMPORT_IMG_EXTENSIONS)

    def can_import(self, file_uris, current_doc=None):
        """
        Check that the specified file looks like an image supported by PIL
        """
        if len(file_uris) <= 0:
            return False
        for file_uri in file_uris:
            file_uri = self.fs.safe(file_uri)
            if not self.check_file_type(file_uri):
                return False
        return True

    def import_doc(self, file_uris, docsearch, current_doc=None):
        """
        Import the specified images
        """
        if (current_doc is None or
                current_doc.is_new or
                not current_doc.can_edit):
            if not current_doc or not current_doc.can_edit:
                current_doc = ImgDoc(self.fs, docsearch.rootdir)
            new_docs = [current_doc]
            upd_docs = []
        else:
            new_docs = []
            upd_docs = [current_doc]
        new_docs_pages = []
        upd_docs_pages = []
        page = None

        file_uris = [self.fs.safe(uri) for uri in file_uris]
        for file_uri in file_uris:
            logger.info("Importing image '%s'" % (file_uri))

            with self.fs.open(file_uri, "rb") as fd:
                img = Image.open(fd)
                img.load()
            page = current_doc.add_page(img, [])

            if new_docs == []:
                upd_docs_pages.append(page)
            else:
                new_docs_pages.append(page)

        return ImportResult(
            imported_file_uris=file_uris,
            select_doc=current_doc, select_page=page,
            new_docs=new_docs, upd_docs=upd_docs,
            new_docs_pages=new_docs_pages,
            upd_docs_pages=upd_docs_pages,
            stats={
                _("Image file(s)"): len(file_uris),
                _("Document(s)"): 0 if new_docs == [] else 1,
                _("Page(s)"): len(new_docs_pages) + len(upd_docs_pages),
            }
        )

    @staticmethod
    def get_select_mime_types():
        return IMG_MIME_TYPES

    @staticmethod
    def get_mime_types():
        return IMG_MIME_TYPES

    def __str__(self):
        return _("Append the image to the current document")


FS = fs.GioFileSystem()
IMPORTERS = [
    PdfDirectoryImporter(FS),
    PdfImporter(FS),
    ImageDirectoryImporter(FS),
    ImageImporter(FS),
]


def get_possible_importers(file_uris, current_doc=None):
    """
    Return all the importer objects that can handle the specified files.

    Possible imports may vary depending on the currently active document
    """
    importers = []
    for importer in IMPORTERS:
        if importer.can_import(file_uris, current_doc):
            importers.append(importer)
    return importers
