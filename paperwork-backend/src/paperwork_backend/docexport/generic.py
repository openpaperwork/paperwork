import logging

from . import (
    AbstractExportPipe,
    AbstractExportPipePlugin,
    ExportData,
    ExportDataType
)
from .. import _


LOGGER = logging.getLogger(__name__)


class DocSetToDoc(AbstractExportPipe):
    def __init__(self, core):
        super().__init__(
            name="doc_set_to_docs",
            input_type=ExportDataType.DOCUMENT_SET,
            output_type=ExportDataType.DOCUMENT
        )
        self.core = core

    def export(self, input_data, result='final', target_file_url=None):
        assert input_data.dtype == ExportDataType.DOCUMENT_SET
        assert not input_data.expanded

        docs = input_data.data
        if result == 'preview':
            docs = docs[:1]
        children = [
            ExportData(ExportDataType.DOCUMENT, doc)
            for doc in docs
        ]
        input_data.set_children(children)
        return input_data

    def get_estimated_size_factor(self, input_data):
        assert input_data.dtype == ExportDataType.DOCUMENT_SET
        return len(input_data.data)

    def __str__(self):
        # this pipe shouldn't ever be visible to end-user
        return "Expand document set into documents (internal)"


class DocToPage(AbstractExportPipe):
    def __init__(self, core):
        super().__init__(
            name="doc_to_pages",
            input_type=ExportDataType.DOCUMENT,
            output_type=ExportDataType.PAGE
        )
        self.core = core

    def can_export_doc(self, doc_url):
        return True

    def export(self, input_data, result='final', target_file_url=None):
        assert input_data.dtype == ExportDataType.DOCUMENT_SET

        docs = input_data.iter(ExportDataType.DOCUMENT)
        for (doc_set, doc) in docs:
            assert not doc.expanded
            nb_pages = self.core.call_success(
                "doc_get_nb_pages_by_url", doc.data[1]
            )
            pages = [
                ExportData(ExportDataType.PAGE, page_idx)
                for page_idx in range(0, nb_pages)
            ]
            doc.set_children(pages)

        return input_data

    def get_estimated_size_factor(self, input_data):
        # average number of pages per document
        assert input_data.dtype == ExportDataType.DOCUMENT_SET
        nb_pages = 0
        nb_docs = len(input_data.data)
        for (doc_id, doc_url) in input_data.data:
            nb_pages += self.core.call_success(
                "doc_get_nb_pages_by_url", doc_url
            )
        return nb_pages / nb_docs

    def __str__(self):
        return _("Page by page processing")


class Plugin(AbstractExportPipePlugin):
    def get_deps(self):
        return [
            {
                'interface': 'pages',
                'defaults': [
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.pdf',
                ],
            },
        ]

    def get_interfaces(self):
        return super().get_interfaces() + [
            "export_pipes_generic",
        ]

    def init(self, core):
        super().init(core)
        self.pipes = [
            DocSetToDoc(self.core),
            DocToPage(self.core),
        ]
