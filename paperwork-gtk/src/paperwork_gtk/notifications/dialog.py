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

from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.gtk_window import GtkWindowListener
import openpaperwork_gtk.deps

from paperwork_gtk.interfaces.notifications import AbstractNotificationBuilder
from paperwork_gtk.interfaces.notifications import Notifications


LOGGER = logging.getLogger(__name__)


class DialogBuilder(AbstractNotificationBuilder):
    def __init__(self, plugin, title):
        self.plugin = plugin
        self.widget_tree = self.plugin.core.call_success(
            GtkResources.gtk_load_widget_tree, "paperwork_gtk.notifications",
            "dialog.glade"
        )
        dialog = self.widget_tree.get_object("dialog")
        dialog.set_title(title)
        dialog.connect("response", self._on_response)

        label = self.widget_tree.get_object("message")
        label.set_text(title)
        label.set_visible(True)

    def _on_response(self, dialog, response):
        dialog.destroy()

    def set_message(self, message):
        label = self.widget_tree.get_object("message")
        label.set_text(message)
        return self

    def set_icon(self, icon):
        self.widget_tree.get_object("dialog").set_icon_name(icon)
        return self

    def add_action(self, action_id, label, callback, *args, **kwargs):
        buttons = self.widget_tree.get_object("buttons")
        button = Gtk.Button.new_with_label(label)
        button.connect("clicked", self._on_click, callback, args, kwargs)
        button.set_visible(True)
        buttons.add(button)
        return self

    def _on_click(self, button, callback, args, kwargs):
        self.widget_tree.get_object("dialog").destroy()
        callback(*args, **kwargs)

    def set_image_from_pixbuf(self, pixbuf):
        img = self.widget_tree.get_object("image")
        img.set_from_pixbuf(pixbuf)
        img.set_visible(True)
        return self

    def show(self):
        dialog = self.widget_tree.get_object("dialog")
        dialog.set_transient_for(self.plugin.windows[-1])
        dialog.set_visible(True)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    GtkWindowListener,
    Notifications,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': GtkResources,
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.windows = []

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def get_notification_builder(self, title, need_actions=False):
        return DialogBuilder(self, title)
