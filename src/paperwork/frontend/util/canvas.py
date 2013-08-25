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

from paperwork.frontend.util import PriorityQueue


class Canvas(Gtk.DrawingArea, Gtk.Scrollable):
    """
    The main canvas is where page(s) are drawn. This is the biggest and most
    important part of the main window.
    """

    # higher is drawn first
    IMG_LAYER = 200
    PROGRESS_BAR_LAYER = 100
    BOX_LAYER = 50
    FADDING_EFFECT_LAYER = 0
    # lower is drawn last

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

        self.components = PriorityQueue()

        self.set_hadjustment(hadj)
        self.set_vadjustment(vadj)

        print "VADJ: %s" % str(self.vadjustment.get_value())

        self.connect("size-allocate", self.__on_size_allocate)
        self.connect("draw", self.__on_draw)
        self.set_size_request(-1, -1)

    def get_hadjustment(self):
        return self.hadjustment

    def set_hadjustment(self, h):
        Gtk.Scrollable.set_hadjustment(self, h)
        h.set_value(5.0)
        h.set_lower(0.0)
        h.set_upper(20.0)
        h.set_step_increment(1.0)
        h.set_page_increment(1.0)
        h.connect("value-changed", self.__on_adjustment_changed)

    def get_vadjustment(self):
        return self.hadjustment

    def set_vadjustment(self, v):
        Gtk.Scrollable.set_vadjustment(self, v)
        v.set_value(5.0)
        v.set_lower(0.0)
        v.set_upper(20.0)
        v.set_step_increment(1.0)
        v.set_page_increment(1.0)
        v.connect("value-changed", self.__on_adjustment_changed)

    def __on_adjustment_changed(self, adjustment):
        print ("ADJ CHANGED: %.2f - %.2f - %.2f"
               % (adjustment.get_lower(),
                  adjustment.get_value(),
                  adjustment.get_upper()))
        pass

    def __on_size_allocate(self, _, size_allocate):
        print "SIZE ALLOCATE: %s" % str((size_allocate.x,
                                         size_allocate.y,
                                         size_allocate.width,
                                         size_allocate.height))

    def __on_draw(self, _, cairo_ctx):
        print "ON DRAW"
        sys.stdout.flush()


GObject.type_register(Canvas)
