import logging

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise

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
    class GObject(object):
        class SignalFlags(object):
            RUN_LAST = 0

        class GObject(object):
            pass


LOGGER = logging.getLogger(__name__)
BLUR_FACTOR = 8


class BlurRenderer(GObject.GObject):
    __gsignals__ = {
        'getting_size': (GObject.SignalFlags.RUN_LAST, None, ()),
        'size_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),
        'img_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),
    }
    OUTLINE = (0.5, 0.5, 0.5)

    def __init__(
            self, core, work_queue_name, wrapped_renderer):
        super().__init__()
        self.core = core
        self.work_queue_name = work_queue_name
        self.wrapped_renderer = wrapped_renderer
        self.blurry = False

        wrapped_renderer.connect(
            "getting_size", self._on_wrapped_getting_size
        )
        wrapped_renderer.connect(
            "size_obtained", self._on_wrapped_size_obtained
        )
        wrapped_renderer.connect(
            "img_obtained", self._on_wrapped_img_obtained
        )

    def __str__(self):
        return f"BlurRenderer({self.wrapped_renderer})"

    def _on_wrapped_getting_size(self, wrapped_renderer):
        self.emit('getting_size')

    def _on_wrapped_size_obtained(self, wrapped_renderer):
        self.emit('size_obtained')

    def _on_wrapped_img_obtained(self, wrapped_renderer):
        self.emit('img_obtained')

    @property
    def size(self):
        return self.wrapped_renderer.size

    def _set_zoom(self, z):
        self.wrapped_renderer.zoom = z

    def _get_zoom(self):
        return self.wrapped_renderer.zoom

    zoom = property(_get_zoom, _set_zoom)

    def start(self):
        self.wrapped_renderer.start()

    def render(self):
        self.wrapped_renderer.render()

    def hide(self):
        self.wrapped_renderer.hide()

    def close(self):
        self.wrapped_renderer.close()

    def draw(self, cairo_ctx):
        renderer = self.wrapped_renderer

        if not self.blurry:
            return renderer.draw(cairo_ctx)

        zoom = self.zoom / BLUR_FACTOR
        reduced_surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32,
            int(renderer.size[0] * zoom),
            int(renderer.size[1] * zoom),
        )
        ctx = cairo.Context(reduced_surface)
        ctx.scale(1 / BLUR_FACTOR, 1 / BLUR_FACTOR)
        renderer.draw(ctx)

        cairo_ctx.save()
        try:
            cairo_ctx.scale(BLUR_FACTOR, BLUR_FACTOR)
            cairo_ctx.set_source_surface(reduced_surface)
            cairo_ctx.paint()
        finally:
            cairo_ctx.save()

    def blur(self):
        self.blurry = True
        self.wrapped_renderer.blur()

    def unblur(self):
        self.blurry = False
        self.wrapped_renderer.unblur()


if GLIB_AVAILABLE:
    GObject.type_register(BlurRenderer)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 2000

    @classmethod
    def get_interfaces(cls):
        return [
            'cairo_url',
            'chkdeps',
        ]

    @classmethod
    def get_deps(cls):
        return [
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

    def cairo_renderer_by_url(
            self, work_queue_name, file_url,
            blur=True, **kwargs):
        if not blur:
            return None

        wrapped_renderer = self.core.call_success(
            "cairo_renderer_by_url",
            work_queue_name, file_url, blur=False, **kwargs
        )
        if wrapped_renderer is None:
            LOGGER.error("Unable to get renderer for '%s' !?", file_url)
            return None

        return BlurRenderer(
            self.core, work_queue_name, wrapped_renderer
        )
