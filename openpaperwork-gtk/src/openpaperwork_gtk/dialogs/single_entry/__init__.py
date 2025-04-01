import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'gtk_dialog_single_entry',
            'gtk_window_listener',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.windows = []

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def gtk_show_dialog_single_entry(
            self, origin, title, original_value, *args, **kwargs):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "openpaperwork_gtk.dialogs.single_entry", "single_entry.glade"
        )
        widget_tree.get_object("entry").set_text(original_value)

        dialog = widget_tree.get_object("dialog")
        dialog.set_title(title)
        dialog.set_transient_for(self.windows[-1])
        dialog.set_modal(True)
        dialog.connect(
            "response", self._on_response, (widget_tree, origin, args, kwargs)
        )
        dialog.show_all()
        return True

    def _on_response(self, dialog, response_id, args):
        (widget_tree, origin, args, kwargs) = args
        new_value = widget_tree.get_object("entry").get_text()
        dialog.destroy()

        if (response_id != 0 and
                response_id != Gtk.ResponseType.ACCEPT and
                response_id != Gtk.ResponseType.OK and
                response_id != Gtk.ResponseType.YES and
                response_id != Gtk.ResponseType.APPLY):
            LOGGER.info("User cancelled")
            r = False
        else:
            r = True
        self.core.call_all(
            "on_dialog_single_entry_reply",
            origin, r, new_value,
            *args, **kwargs
        )
