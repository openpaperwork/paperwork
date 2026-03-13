from openpaperwork_core.interfaces.fs import Fs
import openpaperwork_core.promise

from paperwork_backend.interfaces.doc_import import AbstractFileImporter
from paperwork_backend.interfaces.doc_import import FileImport
from paperwork_backend.interfaces.doc_import import ImportListener
from paperwork_backend.interfaces.doc_transactions import DocTransactionFactory


class BaseFileImporter(AbstractFileImporter):
    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            openpaperwork_core.Dependency(
                interface=DocTransactionFactory,
                defaults=[
                    "paperwork_backend.index.whoosh",
                    "paperwork_backend.doctracker",
                ],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=ImportListener,
                defaults=[],
                optional=True,
            ),
        ]

    def __init__(self, core, file_import, single_file_importer_factory):
        self.core = core
        self.file_import = file_import
        self.single_file_importer_factory = single_file_importer_factory
        self.to_import = list(self._get_importables())

    def get_name(self):
        return self.single_file_importer_factory.get_name()

    def can_import(self):
        return len(self.to_import) > 0

    def get_required_data(self):
        """
        Possible requirements:
        - "password": Document is password-protected. We need the password
          to import it.

        Returns:
            {file_uri: {requirement_a, requirement_b, etc}}
        """
        out = {}
        for (orig_url, file_url) in self.to_import:
            required = self.single_file_importer_factory.get_required_data(
                file_url
            )
            if len(required) <= 0:
                continue
            out[file_url] = required
        return out

    @staticmethod
    def _upd_file_import(imported, file_import: FileImport, orig_uri, file_uri):
        try:
            file_import.ignored_files.remove(orig_uri)
        except ValueError:
            pass
        if imported:
            file_import.imported_files.add(file_uri)
        else:
            file_import.ignored_files.append(file_uri)

    def _make_transactions(self, file_import):
        transactions = []
        self.core.call_all(
            DocTransactionFactory.doc_transaction_start, transactions,
            len(file_import.new_doc_ids) + len(file_import.upd_doc_ids)
        )
        transactions.sort(key=lambda transaction: -transaction.priority)
        return transactions

    def _do_transactions(self, transactions, file_import):
        for doc_id in file_import.new_doc_ids:
            for transaction in transactions:
                transaction.add_doc(doc_id)
        for doc_id in file_import.upd_doc_ids:
            for transaction in transactions:
                transaction.upd_doc(doc_id)
        for transaction in transactions:
            transaction.commit()

    def get_import_promise(self, data=None):
        """
        Return a promise with all the steps required to import files
        specified in `file_import` (see constructor), transactions included.

        Must be scheduled with 'transaction_manager.transaction_schedule()'.

        Arguments:
            data are extra data that may be required
            (see `get_required_data()`)
        """
        if data is None:
            data = {}

        promise = openpaperwork_core.promise.Promise(self.core)

        for (orig_uri, file_uri) in self.to_import:
            promise = promise.then(
                self.single_file_importer_factory.make_importer(
                    self.file_import, file_uri, data
                ).get_promise()
            )
            promise = promise.then(
                self._upd_file_import, self.file_import, orig_uri, file_uri
            )

        promise = promise.then(self._make_transactions, self.file_import)
        promise = promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, self._do_transactions, args=(self.file_import,)
            )
        )

        return promise.then(
            self.core.call_all, ImportListener.on_import_done, self.file_import
        )


class DirectFileImporter(BaseFileImporter):
    """
    Designed to import only explicitly selected files
    """
    def _get_importables(self):
        factory = self.single_file_importer_factory
        for file_uri in self.file_import.ignored_files:
            if factory.is_importable(self.core, file_uri):
                yield (file_uri, file_uri)


class RecursiveFileImporter(BaseFileImporter):
    """
    Assume files to import are actually directories. Look inside those
    directories to find files to import.
    """
    def _get_importables(self):
        factory = self.single_file_importer_factory
        for dir_uri in self.file_import.ignored_files:
            if not self.core.call_success(Fs.fs_isdir, dir_uri):
                continue
            for file_uri in self.core.call_success(Fs.fs_recurse, dir_uri):
                if factory.is_importable(self.core, file_uri):
                    yield (dir_uri, file_uri)

    def get_name(self):
        return self.single_file_importer_factory.get_recursive_name()
