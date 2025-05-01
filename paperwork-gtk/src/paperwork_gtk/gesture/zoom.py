import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.memleak_detector import MemleakDetector
import openpaperwork_core

import openpaperwork_gtk.deps

from paperwork_gtk.interfaces.zoom import Zoom


LOGGER = logging.getLogger(__name__)


class Zoomer:
    def __init__(self, zoomable, adjustment):
        self.adjustment = adjustment
        self.gesture = Gtk.GestureZoom.new(zoomable)

        self.ref_adj_value = 1.0
        self.ref_gesture_value = 1.0

        self.gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.gesture.connect("update", self._on_gesture, adjustment)
        self.gesture.connect("end", self._update_refs)
        self.adjustment.connect("value-changed", self._update_refs)

    def _on_gesture(self, gesture, sequence, adjustment):
        scale = gesture.get_scale_delta()
        adj_scale = (self.ref_adj_value * scale / self.ref_gesture_value)
        LOGGER.debug("Zoom gesture: %f --> %f", scale, adj_scale)
        adjustment.set_value(adj_scale)

    def _update_refs(self, *args, **kwargs):
        self.ref_adj_value = self.adjustment.get_value()
        self.ref_gesture_value = self.gesture.get_scale_delta()
        LOGGER.debug("Ref: %f, %f", self.ref_adj_value, self.ref_gesture_value)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    Zoom,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": MemleakDetector,
                "defaults": [],
                "optional": True,
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        # XXX(Jflesch): Looks like a GObject Introspection bug: if the
        # GtkGesture objects get garbage-collected, the gesture isn't detected
        # anymore. --> We need to keep a reference to those objects as long
        # as we need them.
        self.refs = {}

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_zoomable_widget_new(self, zoomable, adjustment):
        """
        zoomable is the widget on which user can zoom.
        zoom gestures are not applied directly on the widget. They are
        applied on a GtkAdjustment.
        """
        zoomer = Zoomer(zoomable, adjustment)
        self.core.call_all(MemleakDetector.on_objref_track, zoomer)
        self.refs[zoomable] = zoomer

    def on_zoomable_widget_destroy(self, zoomable, adjustment):
        if zoomable in self.refs:
            self.refs.pop(zoomable)
