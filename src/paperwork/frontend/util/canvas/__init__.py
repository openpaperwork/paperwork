"""
The main canvas is where page(s) are drawn. This is the biggest and most
important part of the main window.

Here are the elements that must drawn on it:
    - images (pages, icons)
    - boxes
    - various overlay (progression line, etc)
"""

import copy
import heapq
import sys

from gi.repository import GLib
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

    __gsignals__ = {
        'absolute-button-press-event': (GObject.SignalFlags.RUN_LAST, None,
                                        (GObject.TYPE_PYOBJECT,)),
        'absolute-motion-notify-event': (GObject.SignalFlags.RUN_LAST, None,
                                         (GObject.TYPE_PYOBJECT,)),
        'absolute-button-release-event': (GObject.SignalFlags.RUN_LAST, None,
                                          (GObject.TYPE_PYOBJECT,)),
        'window-moved': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, scrollbars):
        Gtk.DrawingArea.__init__(self)

        hadj = scrollbars.get_hadjustment()
        vadj = scrollbars.get_vadjustment()

        self.size_forced = False
        self.full_size = (1, 1)
        self.visible_size = (1, 1)

        self.drawers = PriorityQueue()

        self.set_hadjustment(hadj)
        self.set_vadjustment(vadj)

        self.add_events(Gdk.EventMask.SCROLL_MASK)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.connect("size-allocate", self.__on_size_allocate)
        self.connect("draw", self.__on_draw)
        self.connect("scroll-event", self.__on_scroll_event)
        self.connect("button-press-event", self.__on_button_pressed)
        self.connect("motion-notify-event", self.__on_motion)
        self.connect("button-release-event", self.__on_button_released)

        self.set_size_request(-1, -1)

        GLib.timeout_add(1000 / 30, self._tick)

    def _tick(self):
        for drawer in self.drawers:
            drawer.on_tick()

    def get_hadjustment(self):
        return self.hadjustment

    def set_hadjustment(self, h):
        Gtk.Scrollable.set_hadjustment(self, h)
        self.set_property("hadjustment", h)
        self.upd_adjustments()
        h.connect("value-changed", self.__on_adjustment_changed)

    def get_vadjustment(self):
        return self.vadjustment

    def set_vadjustment(self, v):
        Gtk.Scrollable.set_vadjustment(self, v)
        self.set_property("vadjustment", v)
        self.upd_adjustments()
        v.connect("value-changed", self.__on_adjustment_changed)

    def __on_adjustment_changed(self, adjustment):
        self.redraw()

    def __on_size_allocate(self, _, size_allocate):
        self.visible_size = (size_allocate.width,
                             size_allocate.height)
        self.upd_adjustments()
        self.redraw()

    def recompute_size(self):
        if self.size_forced:
            return
        (full_x, full_y) = (1, 1)
        for drawer in self.drawers:
            x = drawer.position[0] + drawer.size[0]
            y = drawer.position[1] + drawer.size[1]
            if (full_x < x):
                full_x = x
            if (full_y < y):
                full_y = y
        new_size = (full_x, full_y)
        if (new_size[0] != self.full_size[0]
            or new_size[1] != self.full_size[1]):
            self.full_size = new_size
            self.set_size_request(new_size[0], new_size[1])
            self.upd_adjustments()

    def upd_adjustments(self):
        val_h = float(self.hadjustment.get_value())
        val_v = float(self.vadjustment.get_value())
        max_h = max(float(self.visible_size[0]),
                    float(self.full_size[0]), 100.0)
        max_v = max(float(self.visible_size[1]),
                    float(self.full_size[1]), 100.0)
        if val_h > self.full_size[0]:
            val_h = self.full_size[0]
        if val_v > self.full_size[1]:
            val_v = self.full_size[1]
        self.hadjustment.set_lower(0)
        self.vadjustment.set_lower(0)
        self.hadjustment.set_upper(max_h)
        self.vadjustment.set_upper(max_v)
        self.hadjustment.set_page_size(self.visible_size[0])
        self.vadjustment.set_page_size(self.visible_size[1])
        self.hadjustment.set_value(int(val_h))
        self.vadjustment.set_value(int(val_v))

    def __on_draw(self, _, cairo_ctx):
        self.recompute_size()

        x = int(self.hadjustment.get_value())
        y = int(self.vadjustment.get_value())
        for drawer in self.drawers:
            cairo_ctx.save()
            try:
                drawer.draw(cairo_ctx, (x, y),
                            (self.visible_size[0], self.visible_size[1]))
            finally:
                cairo_ctx.restore()

    def add_drawer(self, drawer):
        drawer.set_canvas(self)

        x = drawer.position[0] + drawer.size[0]
        y = drawer.position[1] + drawer.size[1]

        self.drawers.add(drawer.layer, drawer)
        self.recompute_size()
        self.redraw()

    def get_drawer_at(self, position):
        (x, y) = position

        for drawer in self.drawers:
            pt_a = drawer.position
            pt_b = (drawer.position[0] + drawer.size[0],
                    drawer.position[1] + drawer.size[1])
            if (x >= pt_a[0] and x < pt_b[0]
                and y >= pt_a[1] and y < pt_b[1]):
                return drawer

        return None

    def remove_drawer(self, drawer):
        drawer.hide()
        self.drawers.remove(drawer)
        self.recompute_size()
        self.redraw()

    def remove_all_drawers(self):
        for drawer in self.drawers:
            drawer.hide()
        self.drawers.purge()
        self.recompute_size()
        self.redraw()

    def redraw(self):
        self.queue_draw()

    def __on_scroll_event(self, _, event):
        ops = {
            Gdk.ScrollDirection.UP:
            lambda h, v: (0, v.get_step_increment()),
            Gdk.ScrollDirection.DOWN:
            lambda h, v: (0, -1 * v.get_step_increment()),
            Gdk.ScrollDirection.RIGHT:
            lambda h, v: (h.get_step_incremented(), 0),
            Gdk.ScrollDirection.LEFT:
            lambda h, v: (-1 * h.get_step_increment(), 0),
        }

        if not event.direction in ops:
            return

        ops = ops[event.direction]
        ops = ops(self.hadjustment, self.vadjustment)

        for (op, adj) in [
                (ops[0], self.hadjustment),
                (ops[1], self.vadjustment)
            ]:
            val = adj.get_value()
            val += op
            if val < adj.get_lower():
                val = adj.get_lower()
            if val >= adj.get_upper():
                val = adj.get_upper() - 1
            if val != adj.get_value():
                adj.set_value(val)
        self.emit('window-moved')

    def __get_absolute_event(self, event):
        off_x = int(self.hadjustment.get_value())
        off_y = int(self.vadjustment.get_value())
        event = event.copy()
        event.x += off_x
        event.y += off_y
        return event;

    def __on_button_pressed(self, _, event):
        event = self.__get_absolute_event(event)
        self.emit('absolute-button-press-event', event)

    def __on_motion(self, _, event):
        event = self.__get_absolute_event(event)
        self.emit('absolute-motion-notify-event', event)

    def __on_button_released(self, _, event):
        event = self.__get_absolute_event(event)
        self.emit('absolute-button-release-event', event)

    def __get_position(self):
        return (int(self.hadjustment.get_value()),
                int(self.vadjustment.get_value()))

    position = property(__get_position)

GObject.type_register(Canvas)
