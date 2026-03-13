"""
Draw a Pillow image on top of GtkDrawingArea.
"""

import logging

import openpaperwork_core

from openpaperwork_gtk.interfaces.pillow import Pillow2Cairo
from openpaperwork_gtk.interfaces.pillow import PillowDrawer


LOGGER = logging.getLogger(__name__)


class Drawer:
    BACKGROUND = (0.75, 0.75, 0.75)

    def __init__(self, core, drawing_area, pil_img):
        self.core = core
        self.drawing_area = drawing_area  # expected: Gtk.DrawingArea
        self.img = core.call_success(Pillow2Cairo.pillow_to_surface, pil_img)
        self.draw_connect_id = drawing_area.connect("draw", self.on_draw)

    def stop(self):
        if self.draw_connect_id is not None:
            self.drawing_area.disconnect(self.draw_connect_id)
        self.draw_connect_id = None
        self.img = None  # free the memory

    def on_draw(self, drawing_area, cairo_ctx):
        widget_height = self.drawing_area.get_allocated_height()
        widget_width = self.drawing_area.get_allocated_width()
        factor_w = self.img.surface.get_width() / widget_width
        factor_h = self.img.surface.get_height() / widget_height
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

        # image
        cairo_ctx.save()
        try:
            cairo_ctx.scale(1.0 / factor, 1.0 / factor)
            cairo_ctx.set_source_surface(self.img.surface)
            cairo_ctx.rectangle(
                0, 0,
                self.img.surface.get_width(), self.img.surface.get_height()
            )
            cairo_ctx.clip()
            cairo_ctx.paint()
        finally:
            cairo_ctx.restore()


class Plugin(
    openpaperwork_core.PluginBase,
    PillowDrawer,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Pillow2Cairo,
                defaults=['paperwork_backend.cairo.pillow'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        # drawing area --> Drawer
        self.active_drawers = {}

    def draw_pillow_start(self, drawing_area, pil_img):
        drawer = Drawer(self.core, drawing_area, pil_img)
        self.active_drawers[drawing_area] = drawer
        return drawer

    def draw_pillow_stop(self, drawing_area):
        drawer = self.active_drawers.pop(drawing_area)
        drawer.stop()
        return drawer


if __name__ == "__main__":
    import sys

    import PIL
    import PIL.Image
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk

    img = PIL.Image.open(sys.argv[1])

    core = openpaperwork_core.Core()
    core.load("openpaperwork_core.mainloop.asyncio")
    core.load("openpaperwork_gtk.fs.gio")
    core.load("openpaperwork_core.thread.simple")
    core.load("openpaperwork_core.work_queue.default")
    core.load("paperwork_backend.cairo.pillow")
    core.load("openpaperwork_core.pillow.img")
    core.load("test", sys.modules[__name__])
    core.init()

    window = Gtk.Window()
    window.set_size_request(600, 600)

    drawing_area = Gtk.DrawingArea()
    window.add(drawing_area)

    core.call_success(PillowDrawer.draw_pillow_start, drawing_area, img)

    window.show_all()

    Gtk.main()
