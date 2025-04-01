import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "page_copy_text"


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'action',
            'action_page',
            'action_page_copy_text',
            'chkdeps',
            'selected_boxes_listener',
            'gtk_window_listener',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)

        self.selected_text = ""
        self.windows = []

        if not GLIB_AVAILABLE:
            return

        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._copy_text)
        self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def on_page_boxes_selected(self, doc_id, doc_url, page_id, boxes):
        self.selected_text = " ".join([b.content for b in boxes])

    def _copy_text(self, *args, **kwargs):
        LOGGER.info(
            "Copying %d characters to clipboard", len(self.selected_text)
        )
        clipboard = Gtk.Clipboard.get_default(self.windows[-1].get_display())
        clipboard.set_text(self.selected_text, -1)
