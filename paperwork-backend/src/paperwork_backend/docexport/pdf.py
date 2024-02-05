import logging

import PIL
import PIL.Image

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise

from . import (
    AbstractExportPipe,
    AbstractExportPipePlugin,
    ExportDataType
)
from .. import _


CAIRO_AVAILABLE = False
GI_AVAILABLE = False
GLIB_AVAILABLE = False
PANGO_AVAILABLE = False

try:
    import cairo
    CAIRO_AVAILABLE = True
except (ImportError, ValueError):
    pass

try:
    import gi
    GI_AVAILABLE = True
except (ImportError, ValueError):
    pass

if GI_AVAILABLE:
    try:
        gi.require_version('Pango', '1.0')
        gi.require_version('PangoCairo', '1.0')
        from gi.repository import Pango
        from gi.repository import PangoCairo
        PANGO_AVAILABLE = True
    except (ImportError, ValueError):
        pass


LOGGER = logging.getLogger(__name__)


class PdfDocUrlToPdfUrlExportPipe(AbstractExportPipe):
    """
    Simply copy the PDF we have.
    """
    def __init__(self, core):
        super().__init__(
            name="unmodified_pdf",
            input_type=ExportDataType.DOCUMENT,
            output_type=ExportDataType.OUTPUT_URL_FILE
        )
        self.core = core

    def can_export_doc(self, doc_url):
        pdf_url = self.core.call_success("doc_get_pdf_url_by_url", doc_url)
        return pdf_url is not None

    def export(self, input_data, result='final', target_file_url=None):
        if target_file_url is None:
            (target_file_url, file_desc) = self.core.call_success(
                "fs_mktemp", prefix="paperwork-export-", suffix=".pdf",
                mode="wb", on_disk=True
            )
            file_desc.close()

        list_docs = input_data.iter(ExportDataType.DOCUMENT)
        out_files = []
        for (idx, (doc_set, doc)) in enumerate(list_docs):
            out = target_file_url
            if idx != 0:
                out = target_file_url.rsplit(".", 1)
                out = "{}_{}.{}".format(out[0], idx, out[1])

            assert not doc.expanded
            pdf_url = self.core.call_success(
                "doc_get_pdf_url_by_url", doc.data[1]
            )
            assert pdf_url is not None
            self.core.call_success("fs_copy", pdf_url, out)
            out_files.append(out)
        return out_files

    def get_output_mime(self):
        return ("application/pdf", ("pdf",))

    def __str__(self):
        return _("Original PDF(s)")


class PdfCreator(object):
    def __init__(self, core, target_file_url, page_format, quality):
        self.core = core
        self.page_format = page_format
        self.quality = quality

        self.file_descriptor = core.call_success(
            "fs_open", target_file_url, 'wb'
        )

        self.pdf_surface = cairo.PDFSurface(
            self.file_descriptor, self.page_format[0], self.page_format[1]
        )
        self.pdf_context = cairo.Context(self.pdf_surface)

        self.gc_protection = []  # WORKAROUND(Jflesch): Cairo crash

    def set_page_size(self, img_size):
        # portrait or landscape
        if (img_size[0] < img_size[1]):
            self.pdf_size = (
                min(self.page_format[0], self.page_format[1]),
                max(self.page_format[0], self.page_format[1])
            )
        else:
            self.pdf_size = (
                max(self.page_format[0], self.page_format[1]),
                min(self.page_format[0], self.page_format[1])
            )
        self.pdf_surface.set_size(self.pdf_size[0], self.pdf_size[1])

    def paint_txt(self, boxes, img_size):
        scale_factor_x = self.pdf_size[0] / img_size[0]
        scale_factor_y = self.pdf_size[1] / img_size[1]
        scale_factor = min(scale_factor_x, scale_factor_y)

        for line in boxes:
            for word in line.word_boxes:
                if word.position[0][0] <= 0 and line.position[0][1] <= 0:
                    continue

                box_size = (
                    (word.position[1][0] - word.position[0][0])
                    * scale_factor,
                    (line.position[1][1] - line.position[0][1])
                    * scale_factor
                )
                if 0 in box_size:
                    continue

                layout = PangoCairo.create_layout(self.pdf_context)
                layout.set_text(word.content, -1)

                txt_size = layout.get_size()
                if 0 in txt_size:
                    continue

                txt_factors = (
                    float(box_size[0]) * Pango.SCALE / txt_size[0],
                    float(box_size[1]) * Pango.SCALE / txt_size[1],
                )

                self.pdf_context.save()
                try:
                    self.pdf_context.set_source_rgb(0, 0, 0)
                    self.pdf_context.translate(
                        word.position[0][0] * scale_factor,
                        line.position[0][1] * scale_factor
                    )

                    # make the text use the whole box space
                    self.pdf_context.scale(txt_factors[0], txt_factors[1])

                    PangoCairo.update_layout(self.pdf_context, layout)
                    PangoCairo.show_layout(self.pdf_context, layout)
                finally:
                    self.pdf_context.restore()
        return self

    def paint_img(self, img):
        img_size = img.size
        scale_factor_x = self.pdf_size[0] / img_size[0]
        scale_factor_y = self.pdf_size[1] / img_size[1]
        scale_factor = min(scale_factor_x, scale_factor_y)

        img_surface = self.core.call_success(
            "pillow_to_surface", img,
            intermediate="jpeg", quality=int(self.quality * 100)
        )
        # WORKAROUND(Jflesch):
        # If Cairo supports JPEG embedding, we use
        # cairo.ImageSurface.set_mime_data() instead of the usual Cairo
        # surface functions to draw the image. It seems this function does
        # not increment the ref counter of the surface object
        # --> the Python GC tends to collect it while Cairo is still going
        # to use it to generate the PDF.
        # --> we have to keep a reference on it ourselves, until the page has
        # been generated.
        self.gc_protection.append(img_surface)

        self.pdf_context.save()
        try:
            self.pdf_context.identity_matrix()
            self.pdf_context.scale(scale_factor, scale_factor)
            self.pdf_context.set_source_surface(img_surface.surface)
            self.pdf_context.paint()
        finally:
            self.pdf_context.restore()

    def next_page(self):
        self.pdf_context.show_page()
        self.gc_protection = []  # WORKAROUND(Jflesch): Cairo crash

    def finish(self):
        self.pdf_surface.flush()
        self.pdf_surface.finish()
        self.file_descriptor.close()


class PagesToPdfUrlExportPipe(AbstractExportPipe):
    def __init__(self, core):
        super().__init__(
            name="generated_pdf",
            input_type=ExportDataType.IMG_BOXES,
            output_type=ExportDataType.OUTPUT_URL_FILE
        )
        self.core = core
        self.can_change_quality = True
        self.can_change_page_format = True

    def set_page_format(self, page_format):
        self.page_format = page_format

    def export(self, input_data, result='final', target_file_url=None):
        if target_file_url is None:
            (target_file_url, file_desc) = self.core.call_success(
                "fs_mktemp", prefix="paperwork-export-", suffix=".pdf",
                mode="w", on_disk=True
            )
            # we need the file name, not the file descriptor
            file_desc.close()

        last_doc = None
        doc_idx = 0
        out = target_file_url
        list_img_boxes = input_data.iter(ExportDataType.IMG_BOXES)

        creator = self.core.call_one(
            "mainloop_execute", PdfCreator,
            self.core, target_file_url, self.page_format, self.quality
        )

        out_files = []

        for (doc_set, (doc, (page, img_boxes))) in list_img_boxes:

            if doc.data[1] != last_doc and last_doc is not None:
                # another doc, another output file, another PDFCreator
                self.core.call_one("mainloop_execute", creator.finish)
                out_files.append(out)
                doc_idx += 1
                out = target_file_url.rsplit(".", 1)
                out = "{}_{}.{}".format(out[0], doc_idx, out[1])
                creator = self.core.call_one(
                    "mainloop_execute", PdfCreator,
                    self.core, out, self.page_format, self.quality
                )
            last_doc = doc.data[1]

            (img, boxes) = img_boxes.data
            self.core.call_one(
                "mainloop_execute", creator.set_page_size, img.size
            )
            self.core.call_one(
                "mainloop_execute", creator.paint_txt, boxes,
                img.size
            )
            img_size = img.size
            img_size = (
                int(self.quality * img_size[0]),
                int(self.quality * img_size[1])
            )
            img = img.resize(
                img_size,
                getattr(PIL.Image, 'Resampling', PIL.Image).LANCZOS
            )
            self.core.call_one("mainloop_execute", creator.paint_img, img)
            self.core.call_one("mainloop_execute", creator.next_page)

        self.core.call_one("mainloop_execute", creator.finish)
        out_files.append(out)
        return out_files

    def get_output_mime(self):
        return ("application/pdf", ("pdf",))

    def __str__(self):
        return _("Generated PDF(s)")


class Plugin(AbstractExportPipePlugin):
    def init(self, core):
        super().init(core)
        self.pipes = [
            PdfDocUrlToPdfUrlExportPipe(core),
            PagesToPdfUrlExportPipe(core),
        ]

    def get_interfaces(self):
        return super().get_interfaces() + [
            "chkdeps",
            "export_pipes_pdf",
        ]

    def get_deps(self):
        return super().get_deps() + [
            {
                'interface': 'pillow_to_surface',
                'defaults': ['paperwork_backend.cairo.pillow'],
            },
        ]

    def chkdeps(self, out: dict):
        if not CAIRO_AVAILABLE:
            out['cairo'].update(openpaperwork_core.deps.CAIRO)
        if not GI_AVAILABLE:
            out['gi'].update(openpaperwork_core.deps.GI)
        if not PANGO_AVAILABLE:
            out['pango'].update(openpaperwork_core.deps.PANGO)
