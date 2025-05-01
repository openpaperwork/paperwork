import io
import logging

import PIL
import PIL.Image

from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.memleak_detector import MemleakDetector
from openpaperwork_core.interfaces.perfcheck import Perfcheck
from openpaperwork_core.interfaces.pillow import Pillow
from openpaperwork_core.interfaces.pillow import PillowUtil
from openpaperwork_core.interfaces.urls import Urls
import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise

from paperwork_backend.interfaces.cairo import Cairo2Pillow
from paperwork_backend.interfaces.cairo import Pdf2Cairo


LOGGER = logging.getLogger(__name__)


def surface2image(core, surface):
    """
    Convert a cairo surface into a PIL image
    """
    # XXX(Jflesch): Python 3 problem
    # cairo.ImageSurface.get_data() raises NotImplementedYet ...

    # import PIL.ImageDraw
    #
    # if surface is None:
    #     return None
    # dimension = (surface.get_width(), surface.get_height())
    # img = PIL.Image.frombuffer("RGBA", dimension,
    #                            surface.get_data(), "raw", "BGRA", 0, 1)
    #
    # background = PIL.Image.new("RGB", img.size, (255, 255, 255))
    # background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
    # return background

    core.call_all(Perfcheck.on_perfcheck_start, "surface2image")

    img_io = io.BytesIO()
    surface.surface.write_to_png(img_io)
    img_io.seek(0)
    try:
        img = PIL.Image.open(img_io)
    except PIL.Image.DecompressionBombError as exc:
        LOGGER.warning("Cairo surface is too big", exc_info=exc)
        return core.call_success(PillowUtil.pillow_get_error, "too_big")
    core.call_all(MemleakDetector.on_objref_track, img)
    img.load()

    if "A" not in img.getbands():
        core.call_all(Perfcheck.on_perfcheck_stop, "surface2image", size=img.size)
        return img

    img_no_alpha = PIL.Image.new("RGB", img.size, (255, 255, 255))
    core.call_all(MemleakDetector.on_objref_track, img_no_alpha)
    img_no_alpha.paste(img, mask=img.split()[3])  # 3 is the alpha channel
    core.call_all(
        Perfcheck.on_perfcheck_stop, "surface2image", size=img_no_alpha.size
    )
    return img_no_alpha


class Plugin(
    openpaperwork_core.PluginBase,
    Cairo2Pillow,
    Pillow,
):
    FILE_EXTENSION = ".pdf"

    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            {
                'interface': Pdf2Cairo,
                'defaults': ['paperwork_backend.cairo.poppler'],
            },
            {
                'interface': Mainloop,
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                "interface": MemleakDetector,
                "defaults": [],
                "optional": True,
            },
            {
                "interface": Perfcheck,
                "defaults": [],
                "optional": True,
            },
            {
                'interface': PillowUtil,
                'defaults': ['openpaperwork_core.pillow.util'],
            },
            {
                'interface': Urls,
                'defaults': ['openpaperwork_core.urls'],
            },
        ]

    def _check_is_pdf(self, file_url):
        (url, args) = self.core.call_success(Urls.url_args_split, file_url)
        if not url.lower().endswith(self.FILE_EXTENSION):
            return (None, None, None)

        page_idx = int(args.get("page", 1)) - 1
        password = args.get('password', None)
        if password is not None:
            password = bytes.fromhex(password).decode("utf-8")

        return (file_url, page_idx, password)

    def url_to_pillow(self, file_url):
        (file_url, page_idx, password) = self._check_is_pdf(file_url)
        if file_url is None:
            return None

        pillow = self.core.call_one(  # Poppler is not really thread safe
            Mainloop.mainloop_execute, self._url_to_pillow,
            file_url, page_idx, password
        )
        return pillow

    def cairo_surface_to_pillow(self, surface):
        return surface2image(self.core, surface)

    def _url_to_pillow(self, file_url, page_idx, password):
        surface = self.core.call_success(
            Pdf2Cairo.pdf_page_to_cairo_surface, file_url, page_idx, password
        )
        # WORKAROUND(Jflesch): may occur with corrupted PDFs
        if surface is None:
            LOGGER.error("Failed to convert %s p%d to cairo surface", file_url, page_idx)
            return None

        img = surface2image(self.core, surface)
        surface.surface.finish()
        img.load()
        return img

    def url_to_pillow_promise(self, file_url):
        (doc_url, page_idx, password) = self._check_is_pdf(file_url)
        if doc_url is None:
            return None

        return openpaperwork_core.promise.Promise(
            self.core, self.url_to_pillow, args=(file_url,)
        )

    def pillow_to_url(self, *args, **kwargs):
        # It could be implemented, but there are no known use-cases.
        return None

    def url_to_img_size(self, file_url):
        return None

    def url_to_img_size_promise(self, file_url):
        return None
