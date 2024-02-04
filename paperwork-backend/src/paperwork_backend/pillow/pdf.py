import io
import logging

import PIL
import PIL.Image

import openpaperwork_core
import openpaperwork_core.deps


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

    core.call_all("on_perfcheck_start", "surface2image")

    img_io = io.BytesIO()
    surface.surface.write_to_png(img_io)
    img_io.seek(0)
    try:
        img = PIL.Image.open(img_io)
    except PIL.Image.DecompressionBombError as exc:
        LOGGER.warning("Cairo surface is too big", exc_info=exc)
        return core.call_success("pillow_get_error", "too_big")
    core.call_all("on_objref_track", img)
    img.load()

    if "A" not in img.getbands():
        core.call_all("on_perfcheck_stop", "surface2image", size=img.size)
        return img

    img_no_alpha = PIL.Image.new("RGB", img.size, (255, 255, 255))
    core.call_all("on_objref_track", img_no_alpha)
    img_no_alpha.paste(img, mask=img.split()[3])  # 3 is the alpha channel
    core.call_all(
        "on_perfcheck_stop", "surface2image", size=img_no_alpha.size
    )
    return img_no_alpha


class Plugin(openpaperwork_core.PluginBase):
    FILE_EXTENSION = ".pdf"

    def get_interfaces(self):
        return [
            'page_img_size',
            'pillow',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'pdf_cairo_url',
                'defaults': ['paperwork_backend.cairo.poppler'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'pillow_util',
                'defaults': ['openpaperwork_core.pillow.util'],
            },
            {
                'interface': 'urls',
                'defaults': ['openpaperwork_core.urls'],
            },
        ]

    def _check_is_pdf(self, file_url):
        (url, args) = self.core.call_success("url_args_split", file_url)
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
            "mainloop_execute", self._url_to_pillow,
            file_url, page_idx, password
        )
        return pillow

    def cairo_surface_to_pillow(self, surface):
        return surface2image(self.core, surface)

    def _url_to_pillow(self, file_url, page_idx, password):
        surface = self.core.call_success(
            "pdf_page_to_cairo_surface", file_url, page_idx, password
        )
        # WORKAROUND(Jflesch): may occur with corrupted PDFs
        if surface is None:
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
