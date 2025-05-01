"""
Draws a frame on a GtkDrawingArea. This frame may or may not be resizable.
This is usually used for the scanner calibration dialog or the page image
cropping.
"""

import logging
import math

try:
    import gi
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core

import openpaperwork_gtk.deps

from paperwork_gtk.interfaces.drawers import FrameDrawerFactory


LOGGER = logging.getLogger(__name__)


class Drawer:
    HANDLE_RADIUS = 10
    HANDLE_DEFAULT_COLOR = (0.0, 0.25, 1.0, 0.5)
    HANDLE_HOVER_COLOR = (0.1, 0.75, 0.1, 1.0)
    HANDLE_SELECTED_COLOR = (0.75, 0.1, 0.1, 1.0)
    HANDLE_MIN_DIST = 50

    RECTANGLE_COLOR = (0.0, 0.25, 1.0, 1.0)
    OUTTER_COLOR = (0.0, 0.25, 1.0, 0.25)

    FRAME_CORNERS = [
        (0, 1),
        (0, 3),
        (2, 1),
        (2, 3),
    ]

    def __init__(
            self, core, drawing_area, content_full_size,
            get_frame_cb, set_frame_cb=None):
        """
        Arguments:
        - drawing_area: the drawing area on which the frame must be
          represented
        - content_full_size: the drawing area has its own size, smaller than
          the actual scan or image. We need to know the actual size of the
          content, so we can figure out at which scale the content and the
          frame are to represented.
        - get_frame_cb : callback returning the frame to display relative
          to content_full_size. A callback is provided so we can always have
          an up-to-date value (for instance coming from the configuration).
        """
        self.core = core

        if drawing_area.get_window() is None:
            drawing_area.connect("realize", self.on_realize)
        else:
            self.on_realize(drawing_area)

        self.drawing_area = drawing_area
        self.get_frame_cb = get_frame_cb
        self.set_frame_cb = set_frame_cb
        self.content_full_size = content_full_size
        self.active_handle = None
        self.selected_handle = None

        self.draw_connect_id = drawing_area.connect("draw", self.on_draw)

        self.motion_connect_id = None
        self.press_connect_id = None
        self.release_connect_id = None
        if self.set_frame_cb:
            self.motion_connect_id = drawing_area.connect(
                "motion-notify-event", self.on_motion
            )
            self.press_connect_id = drawing_area.connect(
                "button-press-event", self.on_pressed
            )
            self.release_connect_id = drawing_area.connect(
                "button-release-event", self.on_released
            )

    def stop(self):
        if self.draw_connect_id is not None:
            self.drawing_area.disconnect(self.draw_connect_id)
        if self.motion_connect_id is not None:
            self.drawing_area.disconnect(self.motion_connect_id)
        if self.press_connect_id is not None:
            self.drawing_area.disconnect(self.press_connect_id)
        if self.release_connect_id is not None:
            self.drawing_area.disconnect(self.release_connect_id)
        self.draw_connect_id = None
        self.motion_connect_id = None
        self.press_connect_id = None
        self.release_connect_id = None

    def request_redraw(self):
        self.drawing_area.queue_draw()

    def _get_factor(self):
        widget_height = self.drawing_area.get_allocated_height()
        widget_width = self.drawing_area.get_allocated_width()
        factor_w = self.content_full_size[0] / widget_width
        factor_h = self.content_full_size[1] / widget_height
        factor = max(factor_w, factor_h)
        return factor

    def _get_frame(self):
        factor = self._get_factor()
        frame = self.get_frame_cb()
        if frame is None:
            frame = (
                0, 0, self.content_full_size[0], self.content_full_size[1]
            )
        return (
            frame[0] / factor, frame[1] / factor,
            frame[2] / factor, frame[3] / factor,
        )

    def _get_closest_handle(self, x, y):
        frame = self._get_frame()

        handle_dists = [
            (
                math.hypot(frame[corner_x] - x, frame[corner_y] - y),
                (corner_x, corner_y)
            )
            for (corner_x, corner_y) in self.FRAME_CORNERS
        ]
        handle = min(handle_dists)
        if handle[0] > self.HANDLE_MIN_DIST:
            return None
        return handle[1]

    def on_realize(self, drawing_area, *args, **kwargs):
        mask = (
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK
        )
        drawing_area.add_events(mask)
        drawing_area.get_window().set_events(
            drawing_area.get_window().get_events() | mask
        )

    def on_motion(self, drawing_area, event):
        if self.selected_handle is None:
            active_handle = self._get_closest_handle(event.x, event.y)
            if active_handle != self.active_handle:
                self.request_redraw()
            self.active_handle = active_handle
        else:
            assert self.set_frame_cb is not None
            factor = self._get_factor()
            frame = self.get_frame_cb()
            if frame is not None:
                frame = list(frame)
            else:
                frame = [
                    0, 0, self.content_full_size[0], self.content_full_size[1]
                ]
            x = event.x * factor
            y = event.y * factor
            frame[self.selected_handle[0]] = x
            frame[self.selected_handle[1]] = y
            frame = (
                max(0, min(frame[0], frame[2])),
                max(0, min(frame[1], frame[3])),
                min(self.content_full_size[0], max(frame[0], frame[2])),
                min(self.content_full_size[1], max(frame[1], frame[3])),
            )
            self.set_frame_cb(frame)
            self.request_redraw()

    def on_pressed(self, drawing_area, event):
        self.selected_handle = self._get_closest_handle(event.x, event.y)
        self.request_redraw()

    def on_released(self, drawing_area, event):
        self.selected_handle = None
        self.request_redraw()

    def on_draw(self, drawing_area, cairo_ctx):
        frame = self._get_frame()
        widget_height = self.drawing_area.get_allocated_height()
        widget_width = self.drawing_area.get_allocated_width()

        # outter
        cairo_ctx.save()
        try:
            color = self.OUTTER_COLOR
            cairo_ctx.set_source_rgba(color[0], color[1], color[2], color[3])

            outters = [
                (0, 0, widget_width, frame[1]),
                (0, frame[3], widget_width, widget_height - frame[3]),
                (0, frame[1], frame[0], frame[3] - frame[1]),
                (
                    frame[2], frame[1],
                    widget_width - frame[2], frame[3] - frame[1]
                ),
            ]
            for (x, y, w, h) in outters:
                cairo_ctx.rectangle(x, y, w, h)

            cairo_ctx.fill()
        finally:
            cairo_ctx.restore()

        (x, y, w, h) = (
            frame[0], frame[1],
            frame[2] - frame[0], frame[3] - frame[1]
        )

        # rectangle
        cairo_ctx.save()
        try:
            color = self.RECTANGLE_COLOR
            cairo_ctx.set_source_rgba(color[0], color[1], color[2], color[3])
            cairo_ctx.set_line_width(1.0)
            cairo_ctx.rectangle(x, y, w, h)
            cairo_ctx.stroke()
        finally:
            cairo_ctx.restore()

        if self.set_frame_cb is None:
            return

        # handles
        cairo_ctx.save()
        try:
            for corner in self.FRAME_CORNERS:
                if self.selected_handle == corner:
                    color = self.HANDLE_SELECTED_COLOR
                elif self.active_handle == corner:
                    color = self.HANDLE_HOVER_COLOR
                else:
                    color = self.HANDLE_DEFAULT_COLOR
                cairo_ctx.set_source_rgba(
                    color[0], color[1], color[2], color[3]
                )
                cairo_ctx.arc(
                    frame[corner[0]], frame[corner[1]],
                    self.HANDLE_RADIUS, 0., 2 * math.pi
                )
                cairo_ctx.fill()
        finally:
            cairo_ctx.restore()


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    FrameDrawerFactory,
):
    def __init__(self, core):
        super().__init__(core)
        # drawing area --> Drawer
        self.active_drawers = {}

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def draw_frame_start(
            self, drawing_area, content_full_size,
            get_frame_cb, set_frame_cb=None):
        drawer = Drawer(
            self.core, drawing_area, content_full_size,
            get_frame_cb, set_frame_cb
        )
        self.active_drawers[drawing_area] = drawer
        return drawer

    def draw_frame_stop(self, drawing_area):
        if drawing_area not in self.active_drawers:
            return
        drawer = self.active_drawers.pop(drawing_area)
        drawer.stop()
        return drawer


if __name__ == "__main__":
    import sys
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk

    core = openpaperwork_core.Core()
    core.load("test", sys.modules[__name__])
    core.init()

    window = Gtk.Window()
    window.set_size_request(600, 600)

    box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 20)
    window.add(box)

    drawing_area_a = Gtk.DrawingArea()
    box.pack_start(drawing_area_a, expand=True, fill=True, padding=0)
    drawing_area_b = Gtk.DrawingArea()
    box.pack_start(drawing_area_b, expand=True, fill=True, padding=0)

    frame = (30, 50, 100, 110)

    def get_frame():
        return frame

    def set_frame(f):
        global frame
        frame = f
        drawing_area_a.queue_draw()
        drawing_area_b.queue_draw()

    core.call_success(
        "draw_frame_start", drawing_area_a, (200, 300), get_frame
    )
    core.call_success(
        "draw_frame_start", drawing_area_b, (200, 300), get_frame, set_frame
    )

    window.show_all()

    Gtk.main()
