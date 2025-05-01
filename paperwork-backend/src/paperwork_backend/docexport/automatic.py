from paperwork_backend import _
from paperwork_backend.docexport import (
    AbstractExportPipe,
    AbstractExportPipePlugin,
    ExportData,
    ExportDataType
)
from paperwork_backend.interfaces.doc_pdf import DocPdf
from paperwork_backend.interfaces.export import ExportPipes


class AutomaticPdfExportPipe(AbstractExportPipe):
    """
    Composite pipe that generates PDF using the original PDF if possible.
    It automatically select between:
    - copying the original PDF file (if available and if the doc is unmodified)
    - exporting a generated PDF
    """
    def __init__(self, core):
        super().__init__(
            name="automatic_pdf",
            input_type=ExportDataType.DOCUMENT,
            output_type=ExportDataType.OUTPUT_URL_FILE,
        )
        self.core = core
        self.can_change_quality = True
        self.can_change_page_format = True

        self.pipes_original_pdf = None
        self.pipes_generated_pdf = None

    def _lazy_init(self):
        if self.pipes_original_pdf is None:
            self.pipes_original_pdf = [
                self.core.call_success(ExportPipes.export_get_pipe_by_name, "unmodified_pdf")
            ]
            self.pipes_original_pdf = [x for x in self.pipes_original_pdf if x is not None]

        if self.pipes_generated_pdf is None:
            self.pipes_generated_pdf = [
                self.core.call_success(ExportPipes.export_get_pipe_by_name, "doc_to_pages"),
                self.core.call_success(ExportPipes.export_get_pipe_by_name, "img_boxes"),
                self.core.call_success(ExportPipes.export_get_pipe_by_name, "generated_pdf"),
            ]
            self.pipes_generated_pdf = [x for x in self.pipes_generated_pdf if x is not None]

    def can_export_doc(self, doc_url):
        self._lazy_init()
        return len(self.pipes_original_pdf) > 0 and len(self.pipes_generated_pdf) > 0

    def export(self, input_data, result="final", target_file_url=None):
        self._lazy_init()
        assert input_data.dtype == ExportDataType.DOCUMENT_SET
        list_docs = input_data.iter(ExportDataType.DOCUMENT)
        out_files = []
        for (idx, (doc_set, doc)) in enumerate(list_docs):
            assert doc.dtype == ExportDataType.DOCUMENT
            (doc_id, doc_url) = doc.data

            doc_input = ExportData.build_doc(doc_id, doc_url)

            out_url = target_file_url
            if idx != 0:
                # automatic names files slightly differently: we assume
                # the user is doing a bulk export.
                out_url = target_file_url.rsplit(".", 1)
                out_url = f"{out_url[0]}_{doc_id}.{out_url[1]}"

            pdf_url = self.core.call_success(
                DocPdf.doc_get_pdf_url_by_url, doc_url, allow_mapped=False
            )
            if pdf_url is not None:
                pipes = self.pipes_original_pdf
            else:
                pipes = self.pipes_generated_pdf
            assert len(pipes) > 0

            r = doc_input
            for pipe in pipes:
                if pipe.can_change_quality:
                    pipe.set_quality(self.quality)
                if pipe.can_change_page_format:
                    pipe.set_page_format(self.page_format)
                r = pipe.export(r, result, out_url)
            out_files += r

        return out_files

    def get_output_mime(self):
        return ("application/pdf", ("pdf",))

    def __str__(self):
        return _("Automatic PDF export (original PDF if possible, generated one else)")


class Plugin(AbstractExportPipePlugin):
    @classmethod
    def get_deps(cls):
        return super().get_deps() + [
            {
                'interface': DocPdf,
                'defaults': ['paperwork_backend.model.pdf'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.pipes = [
            AutomaticPdfExportPipe(core),
        ]
