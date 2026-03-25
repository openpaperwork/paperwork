import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core
import openpaperwork_gtk.deps

from openpaperwork_gtk.interfaces.dialogs import GtkSingleEntryDialog
from openpaperwork_gtk.interfaces.dialogs import GtkSingleEntryDialogListener
from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.gtk_window import GtkWindowListener


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    GtkSingleEntryDialog,
    GtkWindowListener,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
            openpaperwork_core.Dependency(
                interface=GtkSingleEntryDialogListener,
                defaults=[],
                optional=True,
            ),
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
            GtkResources.gtk_load_widget_tree,
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
            GtkSingleEntryDialogListener.on_dialog_single_entry_reply,
            origin, r, new_value,
            *args, **kwargs
        )
