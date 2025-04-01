import logging

try:
    import gi
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)


class Zoomer(object):
    ZOOM_INCREMENT = 0.02

    def __init__(self, zoomable, adjustment):
        self.adjustment = adjustment
        if zoomable.get_window() is not None:
            self._enable_events(zoomable)
        else:
            zoomable.connect("realize", self._enable_events)
        zoomable.connect("scroll-event", self._on_scroll)

    def _enable_events(self, zoomable):
        zoomable.add_events(Gdk.EventMask.SCROLL_MASK)
        zoomable.get_window().set_events(
            zoomable.get_window().get_events() | Gdk.EventMask.SCROLL_MASK
        )

    def _on_scroll(self, widget, event):
        if (event.state & Gdk.ModifierType.CONTROL_MASK):
            original = self.adjustment.get_value()
            delta = event.get_scroll_deltas()[2]
            if delta < 0:
                zoom = original + self.ZOOM_INCREMENT
            elif delta > 0:
                zoom = original - self.ZOOM_INCREMENT
            else:
                return False
            LOGGER.debug("Ctrl + Scrolling: zoom %f --> %f", original, zoom)
            self.adjustment.set_value(zoom)
            return True
        # don't know what to do, don't care. Let someone else take care of it
        return False


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'gtk_zoomable',
        ]

    def __init__(self, core):
        super().__init__(core)
        # XXX(Jflesch): Looks like a GObject Introspection bug: if the
        # Zoomer objects get garbage-collected, the signal isn't handled
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
        self.core.call_all("on_objref_track", zoomer)
        self.refs[zoomable] = zoomer

    def on_zoomable_widget_destroy(self, zoomable, adjustment):
        if zoomable in self.refs:
            self.refs.pop(zoomable)
