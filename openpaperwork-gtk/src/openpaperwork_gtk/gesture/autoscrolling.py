"""
Scrolling with the middle mouse button.

Useful for:
- smoother scrolling
- horizontal scrolling: the horizontal scrollbar is blocked by the
  half-transparent lower toolbar
"""

import logging

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.mainloop import Mainloop
import openpaperwork_core

from openpaperwork_gtk.interfaces.gesture import AutoscrollingGesture
import openpaperwork_gtk.deps


GI_AVAILABLE = False
GTK_AVAILABLE = False

try:
    import gi
    GI_AVAILABLE = True
except (ImportError, ValueError):
    pass

if GI_AVAILABLE:
    try:
        gi.require_version('Gdk', '3.0')
        from gi.repository import Gdk
        GTK_AVAILABLE = True
    except (ImportError, ValueError):
        pass


LOGGER = logging.getLogger(__name__)


class AutoScrollingHandler:
    def __init__(self, core, scrollview):
        self.core = core
        self.refcount = 0
        self.mouse_start_position = (0, 0)  # relative to the screen
        self.mouse_position = (0, 0)  # relative to the screen

        self.cursors = {
            'inactive': None,
            'active': None,
        }

        try:
            display = scrollview.get_display()
            self.cursors['active'] = Gdk.Cursor.new_for_display(
                display, Gdk.CursorType.TCROSS
            )
        except TypeError:
            # may not work with pure-Wayland systems
            pass

        self.scrollview = scrollview
        scrollview.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.button_press_id = scrollview.connect(
            "button-press-event", self._on_button_press
        )
        self.button_release_id = scrollview.connect(
            "button-release-event", self._on_button_release
        )
        self.motion_notify_id = scrollview.connect(
            "motion-notify-event", self._on_mouse_motion
        )

    def disable(self):
        self.scrollview.disconnect(self.button_press_id)
        self.scrollview.disconnect(self.button_release_id)
        self.scrollview.disconnect(self.motion_notify_id)

    def _on_tick(self):
        if self.mouse_start_position is None:
            self.refcount -= 1
            return

        hdiff = (self.mouse_position[0] - self.mouse_start_position[0]) / 5
        vdiff = (self.mouse_position[1] - self.mouse_start_position[1]) / 5

        hadj = self.scrollview.get_hadjustment()
        vadj = self.scrollview.get_vadjustment()

        hval = hadj.get_value() + hdiff
        hval = max(hval, hadj.get_lower())
        hval = min(hval, hadj.get_upper())
        hadj.set_value(hval)
        vval = vadj.get_value() + vdiff
        vval = max(vval, vadj.get_lower())
        vval = min(vval, vadj.get_upper())
        vadj.set_value(vval)

        self.core.call_one(Mainloop.mainloop_schedule, self._on_tick, delay_s=0.1)

    def _on_button_press(self, scrollview, event):
        if event.button != 2:
            return
        LOGGER.info("Starting autoscrolling")
        self.mouse_start_position = (event.x_root, event.y_root)
        self.mouse_position = (event.x_root, event.y_root)
        if self.refcount <= 0:
            self.core.call_one(Mainloop.mainloop_schedule, self._on_tick, delay_s=0.1)
        self.refcount += 1
        self.scrollview.get_window().set_cursor(self.cursors['active'])

    def _on_button_release(self, scrollview, event):
        if event.button != 2:
            return
        LOGGER.info("Ending autoscrolling")
        self.mouse_start_position = None
        self.scrollview.get_window().set_cursor(self.cursors['inactive'])

    def _on_mouse_motion(self, scrollview, event):
        if self.mouse_start_position is None:
            return
        self.mouse_position = (event.x_root, event.y_root)


class Plugin(
    openpaperwork_core.PluginBase,
    AutoscrollingGesture,
    Chkdeps,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": Mainloop,
                "defaults": ["openpaperwork_gtk.mainloop.glib"],
            },
        ]

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def gesture_enable_autoscrolling(self, scrollview):
        LOGGER.info("Enabling autoscrolling on %s", scrollview)
        try:
            return AutoScrollingHandler(self.core, scrollview)
        except TypeError as exc:
            # may happen with Wayland
            LOGGER.error("Failed to switch mouse cursor", exc_info=exc)
            return None
