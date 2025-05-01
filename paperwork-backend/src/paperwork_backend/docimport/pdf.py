import logging

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.mainloop import Mainloop
import openpaperwork_core
import openpaperwork_core.promise

from paperwork_backend import _
from paperwork_backend.docimport import (
    DirectFileImporter,
    FileImport,
    RecursiveFileImporter
)
from paperwork_backend.interfaces.doc_import import ImporterFactory
from paperwork_backend.interfaces.doc_pdf import DocPdf
from paperwork_backend.interfaces.index import Index
from paperwork_backend.interfaces.poppler import Poppler


LOGGER = logging.getLogger(__name__)


class SinglePdfImporter:
    def __init__(self, core, file_import, src_file_uri, data):
        self.core = core
        self.file_import = file_import
        self.src_file_uri = src_file_uri
        self.data = data
        self.doc_id = None
        self.doc_url = None

    def _basic_import(self, file_uri):
        file_hash = self.core.call_success(Fs.fs_hash, file_uri)
        other_doc_id = self.core.call_success(
            Index.index_get_doc_id_by_hash, file_hash
        )
        if other_doc_id is not None:
            LOGGER.info("%s has already been imported", file_uri)
            self.file_import.stats[_("Already imported")] += 1
            return False

        LOGGER.info("Importing %s", file_uri)
        (self.doc_id, self.doc_url) = self.core.call_success(
            DocPdf.doc_pdf_import, file_uri,
            password=self.data.get('password'),
            target_doc_id=self.file_import.active_doc_id
        )
        if self.doc_id is None:
            return False
        self.file_import.new_doc_ids.add(self.doc_id)
        self.file_import.stats[_("PDF")] += 1
        self.file_import.stats[_("Documents")] += 1
        return True

    def get_promise(self):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self._basic_import, args=(self.src_file_uri,)
        )


class SinglePdfImporterFactory:
    def __init__(self, plugin):
        self.plugin = plugin
        self.core = plugin.core

    @staticmethod
    def get_name():
        return _("Import PDF")

    @staticmethod
    def get_recursive_name():
        return _("Import PDFs recursively")

    def is_importable(self, core, file_uri):
        mime = core.call_success(Fs.fs_get_mime, file_uri)
        if mime is not None:
            if mime == Plugin.MIME_TYPE:
                return True
            return False
        if file_uri.lower().endswith(self.plugin.FILE_EXTENSION):
            return True

    def get_required_data(self, file_uri):
        try:
            self.core.call_success(Poppler.poppler_open, file_uri, password=None)
            LOGGER.info("%s: not password protected", file_uri)
            return set()
        except Exception:
            # XXX(Jflesch): there is no specific exception type ... :/
            LOGGER.info("%s: password protected", file_uri)
            return {"password"}

    def make_importer(self, file_import, file_uri, data):
        return SinglePdfImporter(self.core, file_import, file_uri, data)


class Plugin(
    openpaperwork_core.PluginBase,
    ImporterFactory,
):
    FILE_EXTENSION = ".pdf"
    MIME_TYPE = "application/pdf"

    @classmethod
    def get_deps(cls):
        return DirectFileImporter.get_deps() + openpaperwork_core.promise.get_deps() + [
            {
                'interface': DocPdf,
                'defaults': ['paperwork_backend.model.pdf'],
            },
            {
                'interface': Fs,
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                "interface": Index,
                "defaults": ["paperwork_backend.index.whoosh"],
                "optional": True,
            },
            {
                'interface': Mainloop,
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                "interface": Poppler,
                "defaults": ["paperwork_backend.poppler.file"],
            },
        ]

    def get_import_mime_types(self, out: set):
        out.add(("PDF", self.MIME_TYPE))
        out.add((_("PDF folder"), "inode/directory"))

    def get_importer(self, out: list, file_import: FileImport):
        importer = DirectFileImporter(
            self.core, file_import, SinglePdfImporterFactory(self)
        )
        if importer.can_import():
            out.append(importer)

        importer = RecursiveFileImporter(
            self.core, file_import, SinglePdfImporterFactory(self)
        )
        if importer.can_import():
            out.append(importer)
