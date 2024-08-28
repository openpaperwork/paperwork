import logging

import openpaperwork_core
import openpaperwork_core.promise

from . import (
    DirectFileImporter,
    FileImport,
    RecursiveFileImporter
)
from .. import _


LOGGER = logging.getLogger(__name__)


class SingleDocImporter(object):
    def __init__(self, plugin, file_import, src_file_uri):
        self.plugin = plugin
        self.core = plugin.core
        self.file_import = file_import
        self.src_file_uri = src_file_uri
        self.doc_id = None
        self.doc_url = None

    def _basic_import(self, file_url):
        file_hash = self.core.call_success("fs_hash", file_url)
        other_doc_id = self.core.call_success(
            "index_get_doc_id_by_hash", file_hash
        )
        if other_doc_id is not None:
            LOGGER.info("%s has already been imported", file_url)
            self.file_import.stats[_("Already imported")] += 1
            return False

        LOGGER.info("Importing %s", file_url)
        (self.doc_id, self.doc_url) = self.core.call_success(
            "doc_convert_and_import", file_url
        )
        self.file_import.new_doc_ids.add(self.doc_id)
        self.file_import.stats[_("Documents")] += 1

        mime = self.core.call_success("fs_get_mime", file_url)
        if mime is not None:
            self.file_import.stats[self.plugin.file_types_by_mime[mime]] += 1
        elif "." in file_url:
            file_ext = file_url.rsplit(".", 1)[-1].lower()
            self.file_import.stats[
                self.plugin.file_types_by_ext[file_ext][1]
            ] += 1

        return True

    def get_promise(self):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self._basic_import, args=(self.src_file_uri,)
        )


class SingleDocImporterFactory(object):
    def __init__(self, plugin):
        self.plugin = plugin
        self.core = plugin.core

    @staticmethod
    def get_name():
        return _("Import office document")

    @staticmethod
    def get_recursive_name():
        return _("Import office documents recursively")

    def is_importable(self, core, file_url):
        mime = core.call_success("fs_get_mime", file_url)
        if mime is not None:
            return mime in self.plugin.file_types_by_mime
        if "." not in file_url:
            return False
        file_ext = file_url.rsplit(".", 1)[-1].lower()
        return file_ext in self.plugin.file_types_by_ext

    def get_required_data(self, file_uri):
        return set()

    def make_importer(self, file_import, file_uri, data):
        return SingleDocImporter(self.plugin, file_import, file_uri)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.file_types_by_ext = {}
        self.file_types_by_mime = {}

    def get_interfaces(self):
        return ["import"]

    def get_deps(self):
        return [
            {
                "interface": "doc_convert_and_import",
                "defaults": ["paperwork_backend.model.converted"],
            },
            {
                "interface": "doc_converter",
                "defaults": ["paperwork_backend.converter.libreoffice"],
            },
            {
                "interface": "fs",
                "defaults": ["openpaperwork_gtk.fs.gio"],
            },
            {
                "interface": "mainloop",
                "defaults": ["openpaperwork_gtk.mainloop.glib"],
            },
            {
                "interface": "thread",
                "defaults": ["openpaperwork_core.thread.simple"],
            },
        ]

    def init(self, core):
        super().init(core)
        file_types = []
        self.core.call_all("converter_get_file_types", file_types)

        self.file_types_by_ext = {}
        for (mime, ext, human_name) in file_types:  # order matters !
            if ext in self.file_types_by_ext:
                continue
            self.file_types_by_ext[ext] = (mime, human_name)

        self.file_types_by_mime = {}
        for (mime, ext, human_name) in file_types:  # order matters !
            if mime in self.file_types_by_mime:
                continue
            self.file_types_by_mime[mime] = human_name

    def get_import_mime_types(self, out: list):
        for (mime, human_desc) in self.file_types_by_ext.values():
            out.add((human_desc, mime))
        if len(self.file_types_by_ext) > 0:
            out.add((_("Office document folder"), "inode/directory"))

    def get_importer(self, out: list, file_import: FileImport):
        importer = DirectFileImporter(
            self.core, file_import, SingleDocImporterFactory(self)
        )
        if importer.can_import():
            out.append(importer)

        importer = RecursiveFileImporter(
            self.core, file_import, SingleDocImporterFactory(self)
        )
        if importer.can_import():
            out.append(importer)
