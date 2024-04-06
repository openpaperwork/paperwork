"""
Plugin to draw scan on GTK widgets.
This code should be on Paperwork-gtk, but Ironscanner needs it to.
"""
from typing import Any
from typing import List
from typing import Tuple

import logging

import openpaperwork_core
import openpaperwork_core.deps

CAIRO_AVAILABLE = False

try:
    import cairo
    CAIRO_AVAILABLE = True
except (ImportError, ValueError):
    pass


LOGGER = logging.getLogger(__name__)


class Drawer(object):
    BACKGROUND = (0.75, 0.75, 0.75)

    def __init__(self, core, drawing_area=None):
        self.core = core
        self.drawing_areas = []
        self.draw_connect_ids = {}

        # expected scan size: note that height may be -1 if unknown
        self.scan_size = (0, 0)

        # Cairo surface size preallocated
        # usually == scan_size unless self.scan_size is weird and smells funny
        self.cairo_size = (0, 0)

        self.last_line = 0
        self.show_scan_border = False
        self.image = None
        self.scan_ended = False

        if drawing_area is not None:
            self.add_drawing_area(drawing_area)

    def add_drawing_area(self, drawing_area):
        self.drawing_areas.append(drawing_area)
        self.draw_connect_ids[drawing_area] = drawing_area.connect(
            "draw", self.on_draw
        )

    def remove_drawing_area(self, drawing_area):
        connect_id = self.draw_connect_ids.pop(drawing_area)
        drawing_area.disconnect(connect_id)
        self.drawing_areas.remove(drawing_area)
        if len(self.drawing_areas) <= 0:
            self.stop()

    def stop(self):
        for (drawing_area, connect_id) in self.draw_connect_ids.items():
            drawing_area.disconnect(connect_id)
        self.draw_connect_ids = {}
        self.drawing_areas = []
        self.image = None  # release the memory

    def request_redraw(self):
        for d in self.drawing_areas:
            d.queue_draw()

    def on_scan_page_start(self, scan_params):
        self.scan_size = (scan_params.get_width(), scan_params.get_height())
        self.last_line = 0
        LOGGER.info(
            "Scan started: %s (expected: %dx%dpx)",
            self.scan_size, self.scan_size[0], self.scan_size[1]
        )
        self.cairo_size = (
            # WORKAROUND(Jflesch): Some scanners (Fujistu mainly) return an
            # image far too big in height. Cairo only allows a maximum image
            # size of 32767 (see #define MAX_IMAGE_SIZE in
            # cairo-image-surface.c)
            min(self.scan_size[0], 32766),
            min(self.scan_size[1], 32766)
            if self.scan_size[1] > 0
            else 32766
        )
        self.image = cairo.ImageSurface(
            cairo.FORMAT_RGB24, self.cairo_size[0], self.cairo_size[1]
        )

        cairo_ctx = cairo.Context(self.image)
        cairo_ctx.set_source_rgb(
            self.BACKGROUND[0], self.BACKGROUND[1], self.BACKGROUND[2]
        )
        cairo_ctx.rectangle(0, 0, self.cairo_size[0], self.cairo_size[1])
        cairo_ctx.fill()

        self.show_scan_border = True
        self.request_redraw()

    def on_scan_page_end(self):
        self.show_scan_border = False
        self.request_redraw()

    def on_scan_chunk(self, img_chunk):
        if self.image is None:
            return

        size = img_chunk.size
        LOGGER.debug("Scan chunk: %s", size)
        img_chunk = self.core.call_success(
            "pillow_to_surface", img_chunk
        )

        cairo_ctx = cairo.Context(self.image)
        cairo_ctx.translate(0, self.last_line)
        cairo_ctx.set_source_surface(img_chunk.surface)
        cairo_ctx.rectangle(0, 0, size[0], size[1])
        cairo_ctx.clip()
        cairo_ctx.paint()

        self.last_line += size[1]
        self.request_redraw()

    def on_draw(self, drawing_area, cairo_ctx):
        widget_height = drawing_area.get_allocated_height()
        widget_width = drawing_area.get_allocated_width()
        factor_w = self.cairo_size[0] / widget_width
        if self.scan_size[1] > 0:
            factor_h = self.cairo_size[1] / widget_height
        else:
            factor_h = self.last_line / widget_height
        factor = max(factor_w, factor_h)

        # background
        cairo_ctx.save()
        try:
            cairo_ctx.set_source_rgb(
                self.BACKGROUND[0], self.BACKGROUND[1], self.BACKGROUND[2]
            )
            cairo_ctx.rectangle(0, 0, widget_width, widget_height)
            cairo_ctx.clip()
            cairo_ctx.paint()
        finally:
            cairo_ctx.restore()

        # chunks
        if self.image is not None:
            cairo_ctx.save()
            try:
                cairo_ctx.scale(1.0 / factor, 1.0 / factor)
                cairo_ctx.set_source_surface(self.image)
                if self.scan_size[1] > 0:
                    cairo_ctx.rectangle(
                        0, 0,
                        self.cairo_size[0], self.cairo_size[1]
                    )
                else:
                    cairo_ctx.rectangle(
                        0, 0,
                        self.cairo_size[0], self.last_line
                    )
                cairo_ctx.clip()
                cairo_ctx.paint()
            finally:
                cairo_ctx.restore()

        # scan border
        if self.show_scan_border:
            cairo_ctx.save()
            try:
                position = int(self.last_line / factor)
                cairo_ctx.set_operator(cairo.OPERATOR_OVER)
                cairo_ctx.set_source_rgba(
                    1.0, 0.0, 0.0, 0.5
                )
                cairo_ctx.set_line_width(10.0)

                cairo_ctx.move_to(0, position)
                cairo_ctx.line_to(widget_width, position)
                cairo_ctx.stroke()
            finally:
                cairo_ctx.restore()


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        # scan id --> Drawer (scan id = None ==> any scan)
        self.active_drawers = {}

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_drawer_scan',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'pillow_to_surface',
                'defaults': ['paperwork_backend.cairo.pillow'],
            },
            {
                'interface': 'scan',
                'defaults': ['paperwork_backend.docscan.libinsane'],
            }
        ]

    def chkdeps(self, out: dict):
        if not CAIRO_AVAILABLE:
            out['cairo'].update(openpaperwork_core.deps.CAIRO)

    def draw_scan_start(self, drawing_area, scan_id=None):
        if scan_id in self.active_drawers:
            drawer = self.active_drawers[scan_id]
        else:
            drawer = Drawer(self.core)
            self.active_drawers[scan_id] = drawer
        drawer.add_drawing_area(drawing_area)
        return drawer

    def draw_scan_stop(self, drawing_area):
        for (k, drawer) in self.active_drawers.items():
            for d in drawer.drawing_areas:
                if d == drawing_area:
                    break
            else:
                continue
            break
        else:
            return None

        drawer.remove_drawing_area(drawing_area)
        if drawer.scan_ended and len(drawer.drawing_areas) <= 0:
            self.active_drawers.pop(k)
        return drawer

    def draw_scan_get_scan_size(self, scan_id):
        active_drawer = self.active_drawers.get(scan_id, None)
        if active_drawer is None:
            return None
        size = active_drawer.cairo_size
        if active_drawer.scan_size[1] < 0:
            size = (size[0], active_drawer.last_line)
        return size

    def on_scan_feed_start(self, scan_id):
        self.core.call_all("on_busy")
        if scan_id not in self.active_drawers:
            return
        # we show the app as busy when the user clicks on 'scan'
        # and we stop the busy indicator when a page is actually scanning
        # instantiate a default drawer to keep track of the size and the chunks
        if scan_id not in self.active_drawers:
            self.active_drawers[scan_id] = Drawer(self.core)

    def on_scan_page_start(self, scan_id, page_nb, scan_params):
        self.core.call_all("on_idle")
        if None in self.active_drawers:
            self.active_drawers[None].on_scan_page_start(scan_params)
        if scan_id in self.active_drawers:
            self.active_drawers[scan_id].on_scan_page_start(scan_params)

    def on_scan_chunk(self, scan_id, scan_params, img_chunk):
        for k in (None, scan_id):
            if k not in self.active_drawers:
                continue
            self.active_drawers[k].on_scan_chunk(img_chunk)

    def on_scan_page_end(self, scan_id, page_nb, img):
        self.core.call_all("on_busy")
        for k in (None, scan_id):
            if k not in self.active_drawers:
                continue
            self.active_drawers[k].on_scan_page_end()
            self.active_drawers[k].scan_ended = True
            if len(self.active_drawers[k].drawing_areas) <= 0:
                self.active_drawers.pop(k)

    def on_scan_feed_end(self, scan_id):
        self.core.call_all("on_idle")
        for k in (None, scan_id):
            if k not in self.active_drawers:
                continue
            self.active_drawers[k].scan_ended = True


if __name__ == "__main__":
    import sys

    import PIL
    import PIL.Image
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    from gi.repository import GLib

    img = PIL.Image.open(sys.argv[1])
    chunks = [
        img.crop((0, line, img.size[1], line + 100))
        for line in range(0, img.size[1], 100)
    ]

    class FakeScanParams(object):
        def __init__(self, img):
            self.img = img

        def get_width(self):
            return self.img.size[0]

        def get_height(self):
            return self.img.size[1]

    class FakeModule(object):
        class Plugin(openpaperwork_core.PluginBase):
            def get_interfaces(self):
                return ['scan']

    scan_params = FakeScanParams(img)

    core = openpaperwork_core.Core()
    core.load("openpaperwork_core.mainloop.asyncio")
    core.load("openpaperwork_core.thread.simple")
    core.load("openpaperwork_core.work_queue.default")
    core.load("openpaperwork_gtk.fs.gio")
    core.load("paperwork_backend.cairo.pillow")
    core.load("openpaperwork_core.pillow.img")
    core._load_module("scan", FakeModule)
    core._load_module("test", sys.modules[__name__])
    core.init()

    window = Gtk.Window()
    window.set_size_request(600, 600)

    drawing_area = Gtk.DrawingArea()
    window.add(drawing_area)

    core.call_all("draw_scan_start", drawing_area, scan_id="pouet")

    calls: List[Tuple[str, str, Any, Any]] = [
        ("on_scan_page_start", "pouet", 0, scan_params),
    ]
    calls += [
        ("on_scan_chunk", "pouet", scan_params, chunk)
        for chunk in chunks
    ]
    calls += [
        ("on_scan_page_end", "pouet", 0, img)
    ]

    calls = 2 * calls

    def wrapper(func, *args):
        func(*args)
        return False

    for (t, call) in enumerate(calls):
        t = t * 500 + 500
        GLib.timeout_add(t, wrapper, core.call_all, *call)

    window.show_all()
    Gtk.main()
