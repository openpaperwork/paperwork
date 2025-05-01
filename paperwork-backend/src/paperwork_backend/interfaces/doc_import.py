# Remark: should be named 'import' as importer also allow importing pages,
# but Python doesn't like it.

from typing import List
import abc
import collections


class FileImport:
    """
    Used as both input and output for importer objects.
    Users may import many files at once and files may not be imported at all
    (for example if they were already imported) --> FileImport objects indicate
    what must still be done, what has been done, and what has not been done at
    all.
    """
    def __init__(self, file_uris_to_import, active_doc_id=None, data=None):
        self.active_doc_id = active_doc_id
        # those attributes will be updated by importers
        self.ignored_files = list(file_uris_to_import)
        self.imported_files = set()
        self.new_doc_ids = set()
        self.upd_doc_ids = set()
        self.stats = collections.defaultdict(lambda: 0)


class ImportListener(abc.ABC):
    @abc.abstractmethod
    def on_import_done(self, file_import: FileImport):
        ...


class AbstractFileImporter(abc.ABC):
    @abc.abstractmethod
    def get_name(self) -> str:
        ...

    @abc.abstractmethod
    def can_import(self) -> bool:
        ...

    @abc.abstractmethod
    def get_required_data(self):
        ...

    @abc.abstractmethod
    def get_import_promise(self, data=None):
        ...


class ImporterFactory(abc.ABC):
    @abc.abstractmethod
    def get_import_mime_types(self, out: list):
        ...

    @abc.abstractmethod
    def get_importer(self, out: List[AbstractFileImporter], file_import: FileImport):
        ...
