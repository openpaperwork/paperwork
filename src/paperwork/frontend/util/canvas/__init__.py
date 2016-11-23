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
import os
import threading

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk

from paperwork.frontend.util import PriorityQueue

from .drawers import CursorDrawer


logger = logging.getLogger(__name__)


CANVAS_ERROR_ON_USELESS = bool(
    int(os.getenv("PAPERWORK_CANVAS_ERROR_ON_USELESS", "0"))
)


class CanvasException(Exception):
    pass


class AbsoluteEvent(object):
    base_event = None
    offset = (0, 0)

    def __init__(self, base_event, offset):
        self.attrs = {}
        for k in dir(base_event):
            self.attrs[k] = getattr(base_event, k)

        self._x = int(base_event.x)
        self._y = int(base_event.y)
        self.offset = offset

    def __getattr__(self, name):
        if name == "x":
            return int(self._x + self.offset[0])
        if name == "y":
            return int(self._y + self.offset[1])
        return self.attrs[name]


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

    TICK_INTERVAL = (1000.0 / 5)

    def __init__(self, scrollbars):
        Gtk.DrawingArea.__init__(self)

        self.redraw_queued = False

        hadj = scrollbars.get_hadjustment()
        vadj = scrollbars.get_vadjustment()

        self.full_size = (1, 1)
        self.visible_size = (1, 1)
        self.mouse_position = (0, 0)

        self.drawers = PriorityQueue()
        self.tick_counter_lock = threading.Lock()

        self.set_hadjustment(hadj)
        self.set_vadjustment(vadj)

        self.add_events(Gdk.EventMask.SCROLL_MASK)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.add_events(Gdk.EventMask.KEY_PRESS_MASK)
        self.add_events(Gdk.EventMask.LEAVE_NOTIFY_MASK)
        super(Canvas, self).connect("size-allocate", self.__on_size_allocate)
        super(Canvas, self).connect("draw", self.__on_draw)
        super(Canvas, self).connect("button-press-event",
                                    self.__on_button_pressed)
        super(Canvas, self).connect("motion-notify-event", self.__on_motion)
        super(Canvas, self).connect("button-release-event",
                                    self.__on_button_released)
        super(Canvas, self).connect("key-press-event", self.__on_key_pressed)
        super(Canvas, self).connect("leave-notify-event", self.__on_mouse_leave)

        hadj.connect("value-changed", self.__on_adjustment_changed)
        vadj.connect("value-changed", self.__on_adjustment_changed)

        self.set_size_request(-1, -1)
        self.set_can_focus(True)

        self.need_ticks = 0
        self.need_stop_ticks = 0

        self._drawer_connections = {}  # drawer --> [('signal', func), ...]

        self.__scroll_origin = (0, 0)
        self.__cursor_drawer = None

    def _tick(self):
        for drawer in self.drawers:
            drawer.on_tick()
        self.__apply_scrolling()
        self.tick_counter_lock.acquire()
        try:
            if self.need_stop_ticks > 0:
                self.need_stop_ticks -= 1
                assert(self.need_ticks >= 0)
                return False
            return (self.need_ticks > 0)
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
            if self.need_ticks <= 0:
                self.need_stop_ticks += 1
            assert(self.need_ticks >= 0)
        finally:
            self.tick_counter_lock.release()

    def get_hadjustment(self):
        return self.hadjustment

    def set_hadjustment(self, h):
        self.upd_adjustments(upd_scrollbar_values=False)
        Gtk.Scrollable.set_hadjustment(self, h)
        self.set_property("hadjustment", h)
        h.connect("value-changed", self.__on_adjustment_changed)

    def get_vadjustment(self):
        return self.vadjustment

    def set_vadjustment(self, v):
        self.upd_adjustments(upd_scrollbar_values=False)
        Gtk.Scrollable.set_vadjustment(self, v)
        self.set_property("vadjustment", v)
        v.connect("value-changed", self.__on_adjustment_changed)

    def __on_adjustment_changed(self, adjustment):
        self.redraw()
        self.emit('window-moved')

    def __on_size_allocate(self, _, size_allocate):
        self.visible_size = (size_allocate.width,
                             size_allocate.height)
        self.upd_adjustments(upd_scrollbar_values=False)
        self.redraw(checked=True)

    def recompute_size(self, upd_scrollbar_values=False):
        (full_x, full_y) = (1, 1)
        for drawer in self.drawers:
            x = drawer.position[0] + drawer.size[0]
            y = drawer.position[1] + drawer.size[1]
            if (full_x < x):
                full_x = x
            if (full_y < y):
                full_y = y
        new_size = (full_x, full_y)
        if (new_size[0] != self.full_size[0] or
                new_size[1] != self.full_size[1]):
            self.full_size = new_size
            self.set_size_request(new_size[0], new_size[1])
            self.upd_adjustments(upd_scrollbar_values)

    def upd_adjustments(self, upd_scrollbar_values=False):
        max_h = max(float(self.visible_size[0]),
                    float(self.full_size[0]), 100.0)
        max_v = max(float(self.visible_size[1]),
                    float(self.full_size[1]), 100.0)

        current = [
            float(self.hadjustment.get_value()),
            float(self.vadjustment.get_value())
        ]
        if not upd_scrollbar_values:
            vals = list(current)
        else:
            if self.mouse_position == (0, 0):
                current_center = [
                    current[0] + (self.visible_size[0] / 2),
                    current[1] + (self.visible_size[1] / 2)
                ]
                # special cases: extreme values
                if current[0] == 0:
                    current_center[0] = 0
                if current[1] == 0:
                    current_center[1] = 0
                if current[0] >= self.hadjustment.get_upper():
                    current_center[0] = self.hadjustment.get_upper()
                if current[1] >= self.vadjustment.get_upper():
                    current_center[1] = self.vadjustment.get_upper()
            else:
                # track the mouse pointer
                current_center = (
                    current[0] + self.mouse_position[0],
                    current[1] + self.mouse_position[1]
                )

            vals = [0, 0]
            for (adj, pos, new_max, idx) in [
                (self.hadjustment, current_center[0], max_h, 0),
                (self.vadjustment, current_center[1], max_v, 1)
            ]:
                adj_min = adj.get_lower()
                adj_max = max(1, adj.get_upper())
                proportional = ((float(pos) - adj_min) / adj_max)
                vals[idx] = int(proportional * new_max)
                if self.mouse_position == (0, 0):
                    vals[idx] -= self.visible_size[idx] / 2
                else:
                    vals[idx] -= self.mouse_position[idx]

        for (adj, pos, new_max, idx) in [
            (self.hadjustment, self.mouse_position[0], max_h, 0),
            (self.vadjustment, self.mouse_position[1], max_v, 1)
        ]:
            if vals[idx] > self.full_size[idx]:
                vals[idx] = self.full_size[idx]
            adj.set_lower(0)
            adj.set_upper(new_max)
            adj.set_page_size(self.visible_size[idx])
            adj.set_value(int(vals[idx]))

    def __on_draw(self, _, cairo_ctx):
        self.redraw_queued = False
        self.recompute_size(upd_scrollbar_values=False)

        for drawer in self.drawers:
            cairo_ctx.save()
            try:
                offset = self.offset
                cairo_ctx.translate(-offset[0], -offset[1])
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
        self.recompute_size(upd_scrollbar_values=False)
        drawer.redraw()

    def get_drawer_at(self, position):
        (x, y) = position

        for drawer in self.drawers:
            pt_a = drawer.position
            pt_b = (drawer.position[0] + drawer.size[0],
                    drawer.position[1] + drawer.size[1])
            if (x >= pt_a[0] and x < pt_b[0] and
                    y >= pt_a[1] and y < pt_b[1]):
                return drawer

        return None

    def connect(self, drawer, signal, func, *args, **kwargs):
        """
        Force the caller to declare a drawer for this connection.
        So when the drawer is removed, we can automatically remove its
        connections

        Arguments:
            drawer --- None allowed
        """
        handler_id = super(Canvas, self).connect(signal, func, *args, **kwargs)
        if drawer is not None:
            if drawer not in self._drawer_connections:
                self._drawer_connections[drawer] = [handler_id]
            else:
                self._drawer_connections[drawer].append(handler_id)

    def disconnect_drawer(self, drawer):
        if drawer not in self._drawer_connections:
            return
        connections = self._drawer_connections.pop(drawer)
        for handler_id in connections:
            super(Canvas, self).disconnect(handler_id)

    def remove_drawer(self, drawer):
        self.disconnect_drawer(drawer)
        drawer.hide()
        self.drawers.remove(drawer)
        self.recompute_size(upd_scrollbar_values=False)
        self.redraw((drawer.position, drawer.size))

    def remove_drawers(self, drawers):
        for drawer in drawers:
            self.disconnect_drawer(drawer)
            drawer.hide()
            self.drawers.remove(drawer)
            self.redraw((drawer.position, drawer.size))
        self.recompute_size(upd_scrollbar_values=False)

    def remove_all_drawers(self):
        for drawer in self.drawers:
            self.disconnect_drawer(drawer)
            drawer.hide()
        self.drawers.purge()
        self.recompute_size(upd_scrollbar_values=False)
        self.redraw(checked=True)

    def redraw(self, area=None, checked=False):
        if self.redraw_queued:
            # a global redraw has already been asked
            return
        if area is None:
            if not checked and CANVAS_ERROR_ON_USELESS:
                raise CanvasException("Unchecked global call to redraw()")
            self.queue_draw()
            self.redraw_queued = True
        else:
            offset = self.offset
            visible = self.visible_size
            position = [area[0][0] - offset[0], area[0][1] - offset[1]]
            size = [area[1][0], area[1][1]]

            if position[0] < 0:
                size[0] += position[0]
                position[0] = 0
            if position[1] < 0:
                size[1] += position[1]
                position[1] = 0

            if (position[0] > visible[0] or position[1] > visible[1] or
                    size[0] <= 0 or size[1] <= 0):
                if CANVAS_ERROR_ON_USELESS:
                    if (visible <= (1, 1)):
                        # Main window isn't visible yet
                        return
                    raise CanvasException(
                        "Useless call to redraw():"
                        " {} --> {} (visible: {})".format(
                            area, (position, size), visible
                        )
                    )
                return

            self.queue_draw_area(
                position[0], position[1],
                size[0], size[1]
            )

    def __get_absolute_event(self, event):
        off_x = int(self.hadjustment.get_value())
        off_y = int(self.vadjustment.get_value())
        return AbsoluteEvent(event, (off_x, off_y))

    def __on_button_pressed(self, _, event):
        if event.button == 2:  # middle button
            self.__scroll_origin = (event.x, event.y)
            logger.info("Start scrolling with 3rd button ({})".format(
                self.__scroll_origin
            ))
            self.start_ticks()
            display = self.get_display()
            try:
                mouse_cursor = Gdk.Cursor.new_from_name(display, "all-scroll")
                origin_cursor = Gdk.Cursor.new_from_name(display, "crosshair")
            except:
                mouse_cursor = Gdk.Cursor.new_for_display(
                    display, Gdk.CursorType.FLEUR
                )
                origin_cursor = Gdk.Cursor.new_for_display(
                    display, Gdk.CursorType.CROSS
                )
            self.get_window().set_cursor(mouse_cursor)

            self.__cursor_drawer = CursorDrawer(
                origin_cursor, (event.x, event.y)
            )
            self.add_drawer(self.__cursor_drawer)
            return False

        self.grab_focus()
        event = self.__get_absolute_event(event)
        self.emit('absolute-button-press-event', event)

    def __on_motion(self, _, event):
        self.mouse_position = (event.x, event.y)
        event = self.__get_absolute_event(event)
        self.emit('absolute-motion-notify-event', event)

    def __on_button_released(self, _, event):
        if self.__scroll_origin != (0, 0):
            self.stop_ticks()
            self.__scroll_origin = (0, 0)
            self.get_window().set_cursor(None)
            self.remove_drawer(self.__cursor_drawer)
        event = self.__get_absolute_event(event)
        self.emit('absolute-button-release-event', event)

    def __scroll(self, offset):
        h = self.hadjustment.get_value()
        v = self.vadjustment.get_value()

        h += offset[0]
        v += offset[1]

        if h != self.hadjustment.get_value():
            if h < self.hadjustment.get_lower():
                h = self.hadjustment.get_lower()
            if h > self.hadjustment.get_upper():
                h = self.hadjustment.get_upper()
        if h != self.hadjustment.get_value():
            self.hadjustment.set_value(h)

        if v != self.vadjustment.get_value():
            if v < self.vadjustment.get_lower():
                v = self.vadjustment.get_lower()
            if v > self.vadjustment.get_upper():
                v = self.vadjustment.get_upper()
        if v != self.vadjustment.get_value():
            self.vadjustment.set_value(v)

        return True

    def __on_key_pressed(self, _, event):
        h_offset = 100
        v_offset = 100

        ops = {
            Gdk.KEY_Left: (-h_offset, 0),
            Gdk.KEY_Right: (h_offset, 0),
            Gdk.KEY_Up: (0, -v_offset),
            Gdk.KEY_Down: (0, +v_offset),
        }
        if event.keyval not in ops:
            return False
        offset = ops[event.keyval]
        return self.__scroll(offset)

    def __on_mouse_leave(self, _, event):
        self.mouse_position = (0, 0)

    def __apply_scrolling(self):
        if (self.__scroll_origin == (0, 0) or self.mouse_position == (0, 0)):
            # no scrolling for now
            return
        SCROLLING_REDUCTION_FACTOR = 2
        scroll_x = self.mouse_position[0] - self.__scroll_origin[0]
        scroll_y = self.mouse_position[1] - self.__scroll_origin[1]
        scroll_x /= SCROLLING_REDUCTION_FACTOR
        scroll_y /= SCROLLING_REDUCTION_FACTOR
        scroll_x = max(min(scroll_x, 50), -50)
        scroll_y = max(min(scroll_y, 50), -50)
        return self.__scroll((scroll_x, scroll_y))

    def __get_position(self):
        return (int(self.hadjustment.get_value()),
                int(self.vadjustment.get_value()))

    position = property(__get_position)

GObject.type_register(Canvas)
