import logging

import openpaperwork_core
import openpaperwork_core.deps


GI_AVAILABLE = False
GDK_AVAILABLE = False

try:
    import gi
    GI_AVAILABLE = True
except (ImportError, ValueError):
    pass

if GI_AVAILABLE:
    try:
        gi.require_version('Gdk', '3.0')
        from gi.repository import Gdk
        GDK_AVAILABLE = True
    except (ImportError, ValueError):
        pass


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'busy',
            'chkdeps',
            'gtk_window_listener',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'gtk_mainwindow',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.refcount = 0
        self.windows = []
        self.realize_handler_id = None

    def chkdeps(self, out: dict):
        if not GDK_AVAILABLE:
            out['gdk'].update(openpaperwork_core.deps.GDK)

    def _set_mouse_cursor(self, offset):
        self.refcount += offset
        assert self.refcount >= 0

        if len(self.windows) <= 0:
            LOGGER.warning(
                "Cannot change mouse cursor: no main window defined"
            )
            return

        if self.refcount > 0:
            LOGGER.info("Mouse cursor --> busy")
            try:
                display = self.windows[-1].get_display()
                cursor = Gdk.Cursor.new_for_display(
                    display, Gdk.CursorType.WATCH
                )
            except TypeError as exc:
                # may happen with Wayland
                LOGGER.error("Failed to switch mouse cursor", exc_info=exc)
                return
        else:
            LOGGER.info("Mouse cursor --> idle")
            cursor = None
        self.windows[-1].get_window().set_cursor(cursor)

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def on_busy(self):
        self._set_mouse_cursor(1)

    def on_idle(self):
        self._set_mouse_cursor(-1)

    def on_widget_busyness_changed(self, widget, busy):
        if busy:
            cursor = None
        else:
            display = widget.get_display()
            cursor = Gdk.Cursor.new_for_display(display, Gdk.CursorType.WATCH)
        window = widget.get_window()

        def _set_cursor(*args, **kwargs):
            window = widget.get_window()
            window.set_cursor(cursor)
            if self.realize_handler_id is not None:
                widget.disconnect(self.realize_handler_id)
                self.realize_handler_id = None

        if window is not None:
            _set_cursor()
        else:
            # assuming the widget will be realized soon
            widget.connect("realize", _set_cursor)
