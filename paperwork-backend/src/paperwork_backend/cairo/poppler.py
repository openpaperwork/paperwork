from typing import Any
from typing import Dict
from typing import Tuple
import logging

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise

# TODO(Jflesch): bad
import paperwork_backend.model.pdf


CAIRO_AVAILABLE = False
GLIB_AVAILABLE = False

try:
    import cairo
    CAIRO_AVAILABLE = True
except (ImportError, ValueError):
    pass

try:
    from gi.repository import GObject
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    # dummy so chkdeps can still be called
    class GObject(object):  # type: ignore[no-redef]
        class SignalFlags(object):
            RUN_LAST = 0

        class GObject(object):
            pass


LOGGER = logging.getLogger(__name__)
DELAY = 0.01
POPPLER_DOCS: Dict[str, Tuple[Any, int]] = {}


class ImgSurface(object):
    # wrapper so it can be weakref
    def __init__(self, surface):
        self.surface = surface


class CairoRenderer(GObject.GObject):
    __gsignals__ = {
        'getting_size': (GObject.SignalFlags.RUN_LAST, None, ()),
        'size_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),
        'img_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),
    }
    OUTLINE = (0.5, 0.5, 0.5)

    def __init__(
            self, core, work_queue_name, file_url, page_idx, password=None):
        global POPPLER_DOCS

        super().__init__()
        self.core = core
        self.work_queue_name = work_queue_name
        self.file_url = file_url
        self.page_idx = page_idx
        self.password = password

        self.visible = False
        self.size = (0, 0)
        self.zoom = 1.0

        if file_url in POPPLER_DOCS:
            (doc, refcount) = POPPLER_DOCS[file_url]
        else:
            LOGGER.info("Opening PDF file {}".format(file_url))
            doc = self.core.call_success(
                "poppler_open", file_url, password=password
            )
            refcount = 0
        POPPLER_DOCS[file_url] = (doc, refcount + 1)

        self.page = doc.get_page(page_idx)

        promise = openpaperwork_core.promise.Promise(
            self.core, self.emit, args=("getting_size",)
        )
        promise = promise.then(openpaperwork_core.promise.Promise(
            self.core, self.page.get_size
        ))
        promise = promise.then(lambda size: (
            size[0] * paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
            size[1] * paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
        ))
        promise.then(self._set_size)

        if page_idx % 25 == 0:
            # Gives back a bit of CPU time to GTK so the GUI remains
            # usable, but not too much so we don't recompute the layout too
            # often
            promise = promise.then(openpaperwork_core.promise.DelayPromise(
                core, DELAY
            ))

        self.get_size_promise = promise

    def __str__(self):
        return "CairoRenderer({} p{})".format(self.file_url, self.page_idx)

    def _set_size(self, size):
        if self.page is None:
            # Document has been closed while we looked for its size
            return
        self.size = size
        self.emit('size_obtained')
        if self.visible:
            self.render(force=True)

    def start(self):
        self.core.call_success(
            "work_queue_add_promise",
            self.work_queue_name, self.get_size_promise
        )

    def render(self, force=False):
        if self.visible and not force:
            return
        self.visible = True
        if self.size == (0, 0):
            return
        self.emit('img_obtained')

    def hide(self):
        self.visible = False

    def close(self):
        global POPPLER_DOCS
        self.hide()
        self.page = None
        self.size = (0, 0)
        (doc, refcount) = POPPLER_DOCS.get(self.file_url, (None, None))
        if refcount is None:
            LOGGER.warning("Double close for %s", self.file_url)
            return
        refcount -= 1
        if refcount > 0:
            POPPLER_DOCS[self.file_url] = (doc, refcount)
            return
        LOGGER.info("Closing PDF file %s", self.file_url)
        POPPLER_DOCS.pop(self.file_url, None)

    def _draw(self, cairo_ctx, zoom):
        try:
            cairo_ctx.save()
            try:
                cairo_ctx.set_source_rgb(1.0, 1.0, 1.0)
                cairo_ctx.scale(zoom, zoom)
                cairo_ctx.rectangle(0, 0, self.size[0], self.size[1])
                cairo_ctx.scale(
                    paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
                    paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
                )
                cairo_ctx.clip()
                cairo_ctx.paint()
                self.page.render(cairo_ctx)

                cairo_ctx.scale(
                    1 / paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
                    1 / paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
                )

                cairo_ctx.set_source_rgb(*self.OUTLINE)
                outline_width = 1 / zoom
                cairo_ctx.set_line_width(outline_width)
                cairo_ctx.rectangle(
                    0, 0,
                    self.size[0] - outline_width, self.size[1] - outline_width
                )
                cairo_ctx.stroke()
            finally:
                cairo_ctx.restore()
        except Exception as exc:
            LOGGER.error("CairoRenderer.draw() failed (PDF)", exc_info=exc)
            # WORKAROUND(Jflesch): with some malformed PDF file, we get an
            # exception on ctx.restore(), but the drawing was actually done.

    def draw(self, cairo_ctx):
        if not self.visible or self.page is None or self.size[0] == 0:
            return

        task = "pdf_to_cairo_draw({}, p{})".format(
            self.file_url, self.page_idx
        )
        self.core.call_all("on_perfcheck_start", task)
        self._draw(cairo_ctx, self.zoom)
        self.core.call_all("on_perfcheck_stop", task, size=self.size)

    def blur(self):
        pass

    def unblur(self):
        pass


if GLIB_AVAILABLE:
    GObject.type_register(CairoRenderer)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000
    FILE_EXTENSION = ".pdf"

    def get_interfaces(self):
        return [
            'cairo_url',
            'chkdeps',
            'page_img_size',
            'pdf_cairo_url',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'poppler',
                'defaults': ['paperwork_backend.poppler.memory'],
            },
            {
                'interface': 'urls',
                'defaults': ['openpaperwork_core.urls'],
            },
        ]

    def chkdeps(self, out: dict):
        if not CAIRO_AVAILABLE:
            out['cairo'].update(openpaperwork_core.deps.CAIRO)
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _check_is_pdf(self, file_url):
        (url, args) = self.core.call_success("url_args_split", file_url)
        if not url.lower().endswith(self.FILE_EXTENSION):
            return (None, None, None)

        password = args.get('password', None)
        if password is not None:
            password = bytes.fromhex(password).decode("utf-8")
        page_idx = int(args.get('page', 1)) - 1
        return (url, page_idx, password)

    def url_to_img_size(self, file_url):
        (file_url, page_idx, password) = self._check_is_pdf(file_url)
        if file_url is None:
            return None

        task = "url_to_img_size({})".format(file_url)
        self.core.call_all("on_perfcheck_start", task)
        doc = self.core.call_success(
            "poppler_open", file_url, password=password
        )
        page = doc.get_page(page_idx)

        base_size = page.get_size()
        size = (  # scale up because default size if too small for reading
            int(base_size[0]) * paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
            int(base_size[1]) * paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
        )

        self.core.call_all("on_perfcheck_stop", task, size=size)
        return size

    def url_to_img_size_promise(self, file_url):
        (page_url, page_idx, password) = self._check_is_pdf(file_url)
        if page_url is None:
            return None

        return openpaperwork_core.promise.Promise(
            self.core, self.url_to_img_size, args=(file_url,)
        )

    def pdf_page_to_cairo_surface(self, file_url, page_idx, password=None):
        task = "pdf_page_to_cairo_surface({} p{})".format(file_url, page_idx)

        self.core.call_all("on_perfcheck_start", task)

        doc = self.core.call_success(
            "poppler_open", file_url, password=password
        )
        page = doc.get_page(page_idx)

        # WORKAROUND(Jflesch):
        # Some corrupted PDFs may cause `page = None` here. (PDF declaring
        # more pages than they actually have).
        if page is None:
            return None

        base_size = page.get_size()
        size = (  # scale up because default size if too small for reading
            int(base_size[0]) * paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
            int(base_size[1]) * paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
        )

        width = int(size[0])
        height = int(size[1])
        factor_w = width / base_size[0]
        factor_h = height / base_size[1]

        surface = ImgSurface(cairo.ImageSurface(
            cairo.FORMAT_ARGB32, width, height
        ))
        self.core.call_all("on_objref_track", surface)

        try:
            ctx = cairo.Context(surface.surface)
            ctx.save()
            try:
                ctx.set_source_rgb(1.0, 1.0, 1.0)
                ctx.rectangle(0, 0, width, height)
                ctx.clip()
                ctx.paint()

                ctx.scale(factor_w, factor_h)
                page.render(ctx)
            finally:
                ctx.restore()
        except Exception as exc:
            LOGGER.error("pdf_page_to_cairo_surface() failed", exc_info=exc)
            # WORKAROUND(Jflesch): with some malformed PDF file, we get an
            # exception on ctx.restore(), but the drawing was actually done.

        self.core.call_all("on_perfcheck_stop", task, size=(width, height))
        return surface

    def url_to_cairo_surface(self, file_url):
        (file_url, page_idx, password) = self._check_is_pdf(file_url)
        if file_url is None:
            return None
        return self.pdf_page_to_cairo_surface(file_url, page_idx, password)

    def url_to_cairo_surface_promise(self, file_url):
        (file_url, page_idx, password) = self._check_is_pdf(file_url)
        if file_url is None:
            return None
        return openpaperwork_core.promise.Promise(
            self.core, self.pdf_page_to_cairo_surface,
            args=(file_url, page_idx, password)
        )

    def cairo_renderer_by_url(self, work_queue_name, file_url, **kwargs):
        (file_url, page_idx, password) = self._check_is_pdf(file_url)
        if file_url is None:
            return None
        return CairoRenderer(
            self.core, work_queue_name, file_url, page_idx, password
        )
