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


class SingleImgImporter(object):
    def __init__(self, factory, file_import, src_file_uri):
        self.factory = factory
        self.core = factory.core
        self.file_import = file_import
        self.src_file_uri = src_file_uri
        self.doc_id = None
        self.doc_url = None

    def _append_file_to_doc(self, file_url, doc_id=None):
        if doc_id is None:
            # new document
            (doc_id, doc_url) = self.core.call_success("storage_get_new_doc")
        else:
            # update existing one
            doc_url = self.core.call_success("doc_id_to_url", doc_id)

        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages is None:
            nb_pages = 0

        # Makes sure it's actually an image and convert it to the expected
        # format
        img = self.core.call_success("url_to_pillow", file_url)
        if img is None:
            LOGGER.error("Failed to load image %s", file_url)
            return (None, None)
        page_url = self.core.call_success(
            "page_get_img_url", doc_url, nb_pages, write=True
        )
        self.core.call_success("pillow_to_url", img, page_url)

        return (doc_id, doc_url)

    def _basic_import(self, file_uri):
        (self.doc_id, self.doc_url) = self._append_file_to_doc(
            file_uri, self.file_import.active_doc_id
        )
        if self.doc_id is None:
            return False

        self.file_import.stats[_("Images")] += 1
        if self.file_import.active_doc_id is None:
            self.file_import.new_doc_ids.add(self.doc_id)
            self.file_import.stats[_("Documents")] += 1
        else:
            self.file_import.upd_doc_ids.add(self.doc_id)
            self.file_import.stats[_("Pages")] += 1

        self.file_import.active_doc_id = self.doc_id

        return True

    def get_promise(self):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self._basic_import, args=(self.src_file_uri,)
        )


class SingleImgImporterFactory(object):
    def __init__(self, plugin):
        self.plugin = plugin
        self.core = plugin.core

    @staticmethod
    def get_name():
        return _("Append the image to the current document")

    @staticmethod
    def get_recursive_name():
        return _(
            "Find the images recursively and import them to the current"
            " document"
        )

    def is_importable(self, core, file_uri):
        mime = core.call_success("fs_get_mime", file_uri)
        if mime is not None:
            mimes = [mime[1] for mime in Plugin.IMG_MIME_TYPES]
            if mime in mimes:
                return True
            return False
        file_ext = file_uri.split(".")[-1].lower()
        if file_ext in self.plugin.FILE_EXTENSIONS:
            return True

    def get_required_data(self, file_uri):
        return set()

    def make_importer(self, file_import, file_uri, data):
        return SingleImgImporter(self, file_import, file_uri)


class Plugin(openpaperwork_core.PluginBase):
    IMG_MIME_TYPES = [
        ("BMP", "image/x-ms-bmp"),
        ("GIF", "image/gif"),
        ("JPEG", "image/jpeg"),
        ("PNG", "image/png"),
        ("TIFF", "image/tiff"),
    ]

    FILE_EXTENSIONS = [
        "bmp",
        "gif",
        "jpeg",
        "jpg",
        "png",
        "tif",
        "tiff",
    ]

    def __init__(self):
        super().__init__()

    def get_interfaces(self):
        return [
            "import"
        ]

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'page_img',
                'defaults': ['paperwork_backend.model.img'],
            },
            {
                'interface': 'pillow',
                'defaults': ['openpaperwork_core.pillow.img'],
            },
            {
                'interface': 'thread',
                'defaults': ['openpaperwork_core.thread.simple'],
            },
        ]

    def get_import_mime_types(self, out: set):
        out.update(self.IMG_MIME_TYPES)

    def get_importer(self, out: list, file_import: FileImport):
        importer = DirectFileImporter(
            self.core, file_import, SingleImgImporterFactory(self)
        )
        if importer.can_import():
            out.append(importer)

        importer = RecursiveFileImporter(
            self.core, file_import, SingleImgImporterFactory(self)
        )
        if importer.can_import():
            out.append(importer)
