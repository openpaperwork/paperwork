"""
Rendering cache: actually used to keep a copy of the rendered page at the
expected size, and only recompute it when the zoom level changes.
Otherwise we overuse Poppler and some PDF may be slow to render correctly
(those with full-page images in it for instance)
"""

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


class CacheRenderer(GObject.GObject):
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

        wrapped_renderer.connect(
            "getting_size", self._on_wrapped_getting_size
        )
        wrapped_renderer.connect(
            "size_obtained", self._on_wrapped_size_obtained
        )
        wrapped_renderer.connect(
            "img_obtained", self._on_wrapped_img_obtained
        )

        self.rendering = None

    def __str__(self):
        return f"CacheRenderer({self.wrapped_renderer})"

    def _on_wrapped_getting_size(self, wrapped_renderer):
        self.emit('getting_size')

    def _on_wrapped_size_obtained(self, wrapped_renderer):
        self.emit('size_obtained')

    def _on_wrapped_img_obtained(self, wrapped_renderer):
        self.rendering = None
        self.emit('img_obtained')

    @property
    def size(self):
        return self.wrapped_renderer.size

    def _set_zoom(self, z):
        self.rendering = None
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
        self.rendering = None
        self.wrapped_renderer.close()

    def draw(self, cairo_ctx):
        if self.rendering is None:
            LOGGER.info("Cache miss. Rendering")
            renderer = self.wrapped_renderer
            rendering_w = int(renderer.size[0] * renderer.zoom)
            rendering_h = int(renderer.size[1] * renderer.zoom)
            rendering = cairo.ImageSurface(
                cairo.FORMAT_ARGB32,
                rendering_w, rendering_h
            )
            rendering_ctx = cairo.Context(rendering)
            renderer.draw(rendering_ctx)
            self.rendering = rendering

        cairo_ctx.save()
        try:
            cairo_ctx.set_source_surface(self.rendering)
            cairo_ctx.paint()
        finally:
            cairo_ctx.restore()

    def blur(self):
        self.rendering = None
        self.wrapped_renderer.blur()

    def unblur(self):
        self.rendering = None
        self.wrapped_renderer.unblur()


if GLIB_AVAILABLE:
    GObject.type_register(CacheRenderer)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000

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
            cache=True, **kwargs):
        if not cache:
            return None

        wrapped_renderer = self.core.call_success(
            "cairo_renderer_by_url",
            work_queue_name, file_url, cache=False, **kwargs
        )
        if wrapped_renderer is None:
            LOGGER.error("Unable to get renderer for '%s' !?", file_url)
            return None

        return CacheRenderer(
            self.core, work_queue_name, wrapped_renderer
        )
