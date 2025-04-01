import logging

import pillowfight


from . import (
    AbstractExportPipePlugin,
    AbstractSimpleTransformExportPipe
)
from .. import _


LOGGER = logging.getLogger(__name__)


class UnpaperExportPipe(AbstractSimpleTransformExportPipe):
    def __init__(self, core):
        super().__init__(core, "unpaper")

    def transform(self, img):
        # Unpaper algorithms in Unpaper's order
        img = pillowfight.unpaper_blackfilter(img)
        img = pillowfight.unpaper_noisefilter(img)
        img = pillowfight.unpaper_blurfilter(img)
        img = pillowfight.unpaper_masks(img)
        img = pillowfight.unpaper_grayfilter(img)
        img = pillowfight.unpaper_border(img)
        return img

    def __str__(self):
        return _("Soft simplification")


class SwtExportPipe(AbstractSimpleTransformExportPipe):
    def __init__(self, core, swt_output_type):
        super().__init__(
            core,
            "swt_soft"
            if swt_output_type == pillowfight.SWT_OUTPUT_ORIGINAL_BOXES
            else "swt_hard"
        )
        self.swt_output_type = swt_output_type

    def transform(self, pil_img):
        pil_img = pil_img.convert("L")
        return pillowfight.swt(pil_img, output_type=self.swt_output_type)

    def __str__(self):
        if self.swt_output_type == pillowfight.SWT_OUTPUT_ORIGINAL_BOXES:
            return _("Hard simplification")
        else:
            return _("Extreme simplification")


class Plugin(AbstractExportPipePlugin):
    @classmethod
    def get_interfaces(cls):
        return []

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'mainloop',
                'defaults': 'openpaperwork_gtk.mainloop.glib',
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.pipes = [
            UnpaperExportPipe(core),
            SwtExportPipe(core, pillowfight.SWT_OUTPUT_ORIGINAL_BOXES),
            SwtExportPipe(core, pillowfight.SWT_OUTPUT_BW_TEXT),
        ]
