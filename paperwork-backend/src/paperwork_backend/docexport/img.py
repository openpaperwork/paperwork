import logging

from . import (
    AbstractExportPipe,
    AbstractExportPipePlugin,
    AbstractSimpleTransformExportPipe,
    ExportData,
    ExportDataType
)
from .. import _


LOGGER = logging.getLogger(__name__)


class ExportDataPage(ExportData):
    """
    Page images takes a lot of memory --> we only load them when actually
    requested.
    """
    def __init__(self, core, doc_id, doc_url, page_idx, progress, final=False):
        super().__init__(ExportDataType.PAGE, page_idx)
        self.expanded = True

        self.core = core
        self.doc_id = doc_id
        self.doc_url = doc_url
        self.page_idx = page_idx
        self.progress = progress
        self.final = final

    def get_children(self):
        # ASSSUMPTION(Jflesch): pages are always requested sequentially
        self.core.call_success(
            "mainloop_schedule", self.core.call_all,
            "on_progress", "export", self.progress,
            _("Exporting {doc_id} p{page_idx} ...").format(
                doc_id=self.doc_id, page_idx=(self.page_idx + 1)
            )
        )

        page_url = (self.core.call_success(
            "page_get_img_url", self.doc_url, self.page_idx
        ))
        assert page_url is not None
        img = self.core.call_success("url_to_pillow", page_url)
        if img is None:
            # WORKAROUND(Jflesch): may happen with corrupted PDFs
            return
        boxes = self.core.call_success(
            "page_get_boxes_by_url", self.doc_url, self.page_idx
        ) or []

        yield ExportData(ExportDataType.IMG_BOXES, (img, boxes))

        if self.final:
            self.core.call_success(
                "mainloop_schedule", self.core.call_all,
                "on_progress", "export", 1.0
            )


class DocToPillowBoxesExportPipe(AbstractExportPipe):
    def __init__(self, core):
        super().__init__(
            name="img_boxes",
            input_type=ExportDataType.PAGE,
            output_type=ExportDataType.IMG_BOXES
        )
        self.core = core

    def can_export_page(self, doc_url, page_nb):
        return True

    def export(self, input_data, result='final', target_file_url=None):
        assert input_data.dtype == ExportDataType.DOCUMENT_SET

        docs = input_data.iter(ExportDataType.DOCUMENT)
        docs = list(docs)

        self.core.call_success(
            "mainloop_schedule", self.core.call_all,
            "on_progress", "export", 0.0,
            _("Exporting ...")
        )

        total_pages = 0
        for (doc_set, doc) in docs:
            assert doc.expanded
            total_pages += len(doc.get_children())

        nb_pages = 0
        last_page = None
        for (doc_set, doc) in docs:
            assert doc.expanded

            # replace the document page list by objects that will
            # generate their children (img+boxes) on-the-fly.
            new_pages = [
                ExportDataPage(
                    self.core, doc.data[0], doc.data[1], page.data,
                    (nb_pages + idx) / total_pages
                )
                for (idx, page) in enumerate(doc.get_children())
            ]
            doc.set_children(new_pages)
            nb_pages += len(new_pages)
            last_page = new_pages[-1]
        last_page.final = True

        return input_data

    def __str__(self):
        return _("Split page(s) into image(s) and text(s)")


class PageToImageExportPipe(AbstractExportPipe):
    def __init__(self, core, name, format, file_extensions, mime, has_quality):
        super().__init__(
            name=name,
            input_type=ExportDataType.IMG_BOXES,
            output_type=ExportDataType.OUTPUT_URL_FILE,
        )
        self.can_change_quality = has_quality
        self.format = format
        self.file_extensions = file_extensions
        self.mime = mime
        self.core = core

    def export(self, input_data, result='final', target_file_url=None):
        if target_file_url is None:
            (target_file_url, file_desc) = self.core.call_success(
                "fs_mktemp", prefix="paperwork-export-",
                suffix="." + self.file_extensions[0], mode="w"
            )
            file_desc.close()

        list_img_boxes = input_data.iter(ExportDataType.IMG_BOXES)

        out_files = []
        for (doc_set, (doc, (page, img_boxes))) in list_img_boxes:
            out = target_file_url
            if len(out_files) != 0:
                out = target_file_url.rsplit(".", 1)
                out = "{}_{}.{}".format(out[0], len(out_files), out[1])

            self.core.call_success(
                "pillow_to_url", img_boxes.data[0], out,
                format=self.format, quality=self.quality
            )
            out_files.append(out)
        return out_files

    def get_output_mime(self):
        return (self.mime, self.file_extensions)

    def __str__(self):
        return _("Image file ({})".format(self.format))


class BlackAndWhiteExportPipe(AbstractSimpleTransformExportPipe):
    def __init__(self, core):
        super().__init__(core, "bw")

    def transform(self, pil_img):
        pil_img = pil_img.convert("L")  # to grayscale
        pil_img = pil_img.point(lambda x: 0 if x < 128 else 255, '1')
        return pil_img

    def __str__(self):
        return _("Black & White")


class GrayscaleExportPipe(AbstractSimpleTransformExportPipe):
    def __init__(self, core):
        super().__init__(core, "grayscale")

    def transform(self, pil_img):
        return pil_img.convert("L")

    def __str__(self):
        return _("Grayscale")


class Plugin(AbstractExportPipePlugin):
    def init(self, core):
        super().init(core)
        self.pipes = [
            BlackAndWhiteExportPipe(core),
            DocToPillowBoxesExportPipe(core),
            GrayscaleExportPipe(core),
            PageToImageExportPipe(
                core, "bmp", "BMP", ("bmp",), "image/x-ms.bmp", False
            ),
            PageToImageExportPipe(
                core, "gif", "GIF", ("gif",), "image/gif", False
            ),
            PageToImageExportPipe(
                core, "jpeg", "JPEG", ("jpeg", "jpg"), "image/jpeg", True
            ),
            PageToImageExportPipe(
                core, "png", "PNG", ("png",), "image/png", False
            ),
            PageToImageExportPipe(
                core, "tiff", "TIFF", ("tiff", "tif"), "image/tiff", False
            ),
        ]

    def get_interfaces(self):
        return super().get_interfaces() + [
            "export_pipes_img",
        ]

    def get_deps(self):
        return [
            {
                'interface': 'doc_text',
                'defaults': [
                    # load also model.img because model.pdf will
                    # satisfy the interface 'page_img' anyway
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.pdf',
                ],
            },
            {
                'interface': 'page_img',
                'defaults': [
                    # load also model.hocr because model.pdf will
                    # satisfy the interface 'doc_text' anyway
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.pdf',
                ],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'pillow',
                'defaults': [
                    'openpaperwork_core.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ],
            },
        ]
