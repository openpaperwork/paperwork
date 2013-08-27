"""
The main canvas is where page(s) are drawn. This is the biggest and most
important part of the main window.

Here are the elements that must drawn on it:
    - images (pages, icons)
    - boxes
    - various overlay (progression line, etc)
"""

import heapq
import sys

from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk

from paperwork.backend.util import image2surface
from paperwork.frontend.util import PriorityQueue


class Canvas(Gtk.DrawingArea, Gtk.Scrollable):
    """
    The main canvas is where page(s) are drawn. This is the biggest and most
    important part of the main window.
    """
    hadjustment = GObject.property(type=Gtk.Adjustment,
                                   default=Gtk.Adjustment(),
                                   flags=GObject.PARAM_READWRITE)
    hscroll_policy = GObject.property(type=Gtk.ScrollablePolicy,
                                      default=Gtk.ScrollablePolicy.MINIMUM,
                                      flags=GObject.PARAM_READWRITE)
    vadjustment = GObject.property(type=Gtk.Adjustment,
                                   default=Gtk.Adjustment(),
                                   flags=GObject.PARAM_READWRITE)
    vscroll_policy = GObject.property(type=Gtk.ScrollablePolicy,
                                      default=Gtk.ScrollablePolicy.MINIMUM,
                                      flags=GObject.PARAM_READWRITE)

    def __init__(self, hadj, vadj):
        Gtk.DrawingArea.__init__(self)

        self.full_size_x = 0
        self.full_size_y = 0
        self.visible_size_x = 0
        self.visible_size_y = 0

        self.drawers = PriorityQueue()

        self.set_hadjustment(hadj)
        self.set_vadjustment(vadj)

        self.connect("size-allocate", self.__on_size_allocate)
        self.connect("draw", self.__on_draw)

        self.set_size_request(-1, -1)

    def get_hadjustment(self):
        return self.hadjustment

    def set_hadjustment(self, h):
        Gtk.Scrollable.set_hadjustment(self, h)
        self.set_property("hadjustment", h)
        h.set_lower(0.0)
        h.set_upper(float(self.full_size_x))
        h.set_step_increment(10.0)
        h.set_page_increment(100.0)  # TODO(Jflesch)
        h.set_page_size(0.0)
        h.connect("value-changed", self.__on_adjustment_changed)

    def get_vadjustment(self):
        return self.hadjustment

    def set_vadjustment(self, v):
        Gtk.Scrollable.set_vadjustment(self, v)
        self.set_property("vadjustment", v)
        v.set_lower(0.0)
        v.set_upper(float(self.full_size_y))
        v.set_step_increment(10.0)
        v.set_page_increment(100.0)  # TODO(Jflesch)
        v.set_page_size(0.0)
        v.connect("value-changed", self.__on_adjustment_changed)

    def __on_adjustment_changed(self, adjustment):
        self.queue_draw()

    def __on_size_allocate(self, _, size_allocate):
        self.visible_size_x = size_allocate.width
        self.visible_size_y = size_allocate.height
        self.upd_adjustments()
        self.queue_draw()

    def upd_adjustments(self):
        self.hadjustment.set_upper(float(self.full_size_x))
        self.vadjustment.set_upper(float(self.full_size_y))
        self.hadjustment.set_page_size(self.visible_size_x)
        self.vadjustment.set_page_size(self.visible_size_y)

    def __on_draw(self, _, cairo_ctx):
        x = int(self.hadjustment.get_value())
        y = int(self.vadjustment.get_value())

        for drawer in self.drawers:
            cairo_ctx.save()
            try:
                drawer.draw(cairo_ctx, (x, y),
                            (self.visible_size_x, self.visible_size_y))
            finally:
                cairo_ctx.restore()

    def add_drawer(self, drawer):
        drawer.set_canvas(self)

        x = drawer.position[0] + drawer.size[0]
        y = drawer.position[1] + drawer.size[1]

        full_size_changed = False
        if (x > self.full_size_x):
            self.full_size_x = x
            full_size_changed = True
        if (y > self.full_size_y):
            self.full_size_y = y
            full_size_changed = True
        if full_size_changed:
            self.set_size_request(self.full_size_x, self.full_size_y)
            self.upd_adjustments()

        self.drawers.add(drawer.layer, drawer)

        self.queue_draw()


GObject.type_register(Canvas)
