#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2014  Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.

"""
The main canvas is where page(s) are drawn. This is the biggest and most
important part of the main window.

Here are the elements that must drawn on it:
    - images (pages, icons)
    - boxes
    - various overlay (progression line, etc)
"""

import logging
import threading

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk

from paperwork.frontend.util import PriorityQueue


logger = logging.getLogger(__name__)


class Canvas(Gtk.DrawingArea, Gtk.Scrollable):

    """
    Canvas are area where Drawer can draw:

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

    TICK_INTERVAL = (1000 / 10)

    def __init__(self, scrollbars):
        Gtk.DrawingArea.__init__(self)

        hadj = scrollbars.get_hadjustment()
        vadj = scrollbars.get_vadjustment()

        self.full_size = (1, 1)
        self.visible_size = (1, 1)

        self.drawers = PriorityQueue()
        self.tick_counter_lock = threading.Lock()

        self.set_hadjustment(hadj)
        self.set_vadjustment(vadj)

        self.add_events(Gdk.EventMask.SCROLL_MASK)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.connect("size-allocate", self.__on_size_allocate)
        self.connect("draw", self.__on_draw)
        self.connect("button-press-event", self.__on_button_pressed)
        self.connect("motion-notify-event", self.__on_motion)
        self.connect("button-release-event", self.__on_button_released)
        self.connect("key-press-event", self.__on_key_pressed)

        hadj.connect("value-changed", self.__on_adjustment_changed)
        vadj.connect("value-changed", self.__on_adjustment_changed)

        self.set_size_request(-1, -1)
        self.set_can_focus(True)

        self.need_ticks = 0

    def _tick(self):
        for drawer in self.drawers:
            drawer.on_tick()
        self.tick_counter_lock.acquire()
        try:
            if self.need_ticks > 0:
                GLib.timeout_add(self.TICK_INTERVAL, self._tick)
        finally:
            self.tick_counter_lock.release()

    def start_ticks(self):
        self.tick_counter_lock.acquire()
        try:
            self.need_ticks += 1
            if self.need_ticks == 1:
                GLib.timeout_add(self.TICK_INTERVAL, self._tick)
            logger.info("Animators: %d" % self.need_ticks)
        finally:
            self.tick_counter_lock.release()

    def stop_ticks(self):
        self.tick_counter_lock.acquire()
        try:
            self.need_ticks -= 1
            logger.info("Animators: %d" % self.need_ticks)
            assert(self.need_ticks >= 0)
        finally:
            self.tick_counter_lock.release()

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
        self.emit('window-moved')

    def __on_size_allocate(self, _, size_allocate):
        self.visible_size = (size_allocate.width,
                             size_allocate.height)
        self.upd_adjustments()
        self.redraw()

    def recompute_size(self):
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

        for drawer in self.drawers:
            cairo_ctx.save()
            try:
                drawer.draw(cairo_ctx)
            finally:
                cairo_ctx.restore()

    def __get_offset(self):
        x = int(self.hadjustment.get_value())
        y = int(self.vadjustment.get_value())
        return (x, y)

    offset = property(__get_offset)

    def __get_visible_size(self):
        return self.visible_size

    size = property(__get_visible_size)

    def add_drawer(self, drawer):
        drawer.set_canvas(self)

        self.drawers.add(drawer.layer, drawer)
        drawer.show()
        self.recompute_size()
        self.redraw((drawer.relative_position, drawer.relative_size))

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

    def remove_drawers(self, drawers):
        for drawer in drawers:
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

    def redraw(self, area=None):
        if area is None:
            self.queue_draw()
        else:
            self.queue_draw_area(area[0][0], area[0][1], area[1][0], area[1][1])

    def __get_absolute_event(self, event):
        off_x = int(self.hadjustment.get_value())
        off_y = int(self.vadjustment.get_value())
        event = event.copy()
        event.x += off_x
        event.y += off_y
        return event

    def __on_button_pressed(self, _, event):
        self.grab_focus()
        event = self.__get_absolute_event(event)
        self.emit('absolute-button-press-event', event)

    def __on_motion(self, _, event):
        event = self.__get_absolute_event(event)
        self.emit('absolute-motion-notify-event', event)

    def __on_button_released(self, _, event):
        event = self.__get_absolute_event(event)
        self.emit('absolute-button-release-event', event)

    def __on_key_pressed(self, _, event):
        h = self.hadjustment.get_value()
        v = self.vadjustment.get_value()
        h_offset = 100
        v_offset = 100
        v_page = self.vadjustment.get_page_size()

        ops = {
            Gdk.KEY_Left: lambda: (h - h_offset, v),
            Gdk.KEY_Right: lambda: (h + h_offset, v),
            Gdk.KEY_Up: lambda: (h, v - v_offset),
            Gdk.KEY_Down: lambda: (h, v + v_offset),
            Gdk.KEY_Page_Up: lambda: (h, v - v_page),
            Gdk.KEY_Page_Down: lambda: (h, v + v_page),
        }
        if event.keyval not in ops:
            return False

        (h, v) = ops[event.keyval]()
        if h != self.hadjustment.get_value():
            if h < self.hadjustment.get_lower():
                h = self.hadjustment.get_lower()
            if h > self.hadjustment.get_upper():
                h = self.hadjustment.get_upper()
            self.hadjustment.set_value(h)
        if v != self.vadjustment.get_value():
            if v < self.vadjustment.get_lower():
                v = self.vadjustment.get_lower()
            if v > self.vadjustment.get_upper():
                v = self.vadjustment.get_upper()
            self.vadjustment.set_value(v)
        return True

    def __get_position(self):
        return (int(self.hadjustment.get_value()),
                int(self.vadjustment.get_value()))

    position = property(__get_position)

GObject.type_register(Canvas)
