import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.uncaught_exception_listener import UncaughtExceptionListener
import openpaperwork_core

from openpaperwork_gtk import deps
from openpaperwork_gtk.interfaces.bug_report import GtkBugReportDisplay
from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.gtk_window import GtkWindowListener


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    GtkWindowListener,
    UncaughtExceptionListener,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': GtkBugReportDisplay,
                'defaults': ['openpaperwork_gtk.bug_report'],
            },
            {
                'interface': GtkResources,
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.nb_dialogs = 3
        self.windows = []
        self.visible = False

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(deps.GTK)

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def on_uncaught_exception(self, exc_info):
        if exc_info[-1] is None:
            LOGGER.warning("No stacktrace. Won't display error dialog")
            return

        if self.visible:
            LOGGER.warning(
                "Error dialog currently displayed. Won't display another one"
            )
            return

        if self.nb_dialogs <= 0:
            LOGGER.warning(
                "Too many error dialogs displayed. Won't display them anymore"
            )
            return

        LOGGER.info("Uncaught exception. Showing error dialog")

        content = repr(exc_info[1])

        widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree, "openpaperwork_gtk.uncaught_exception",
            "uncaught_exception.glade"
        )
        if widget_tree is None:
            LOGGER.warning("Failed to load widget tree")
            return

        widget_tree.get_object("error").set_text(content, -1)
        dialog = widget_tree.get_object("dialog")
        if len(self.windows) > 0:
            dialog.set_transient_for(self.windows[-1])
        dialog.connect("response", self._on_response)
        dialog.show_all()

        self.visible = True
        self.nb_dialogs -= 1

    def _on_response(self, dialog, response_id):
        LOGGER.info("Response: %s", response_id)

        dialog.destroy()
        self.visible = False

        if response_id != Gtk.ResponseType.ACCEPT:
            return

        self.core.call_all(GtkBugReportDisplay.open_bug_report)
