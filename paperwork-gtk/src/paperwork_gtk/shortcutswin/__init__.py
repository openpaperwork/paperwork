import collections
import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.fs import Fs
import openpaperwork_core
import openpaperwork_gtk.deps

from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.gtk_window import GtkWindowListener
from openpaperwork_gtk.interfaces.screenshot import Screenshot
from openpaperwork_gtk.interfaces.screenshot import ScreenshotProvider

from paperwork_gtk.interfaces.keyboard_shortcut import KeyboardShortcutCollector
from paperwork_gtk.interfaces.shortcuts import AppShortcutHelp


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    AppShortcutHelp,
    Chkdeps,
    GtkWindowListener,
    KeyboardShortcutCollector,
    ScreenshotProvider,
):
    def __init__(self, core):
        super().__init__(core)
        self.windows = []
        self.groups = collections.defaultdict(list)
        self.widget_tree = None

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=["openpaperwork_gtk.fs.gio"],
            ),
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
            openpaperwork_core.Dependency(
                interface=Screenshot,
                defaults=['openpaperwork_gtk.screenshots'],
            ),
        ]

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def app_shortcut_add(
            self, shortcut_group, shortcut_desc, shortcut_keys, action_name):
        self.shortcut_help_add(
            shortcut_group, shortcut_desc, shortcut_keys, action_name
        )

    def shortcut_help_add(
            self, shortcut_group, shortcut_desc, shortcut_keys, action_name):
        LOGGER.info(
            "Keyboard shortcut: %s --> %s:%s",
            shortcut_keys, shortcut_group, shortcut_desc
        )
        group = self.groups[shortcut_group]
        group.append((
            shortcut_desc, shortcut_keys, action_name
        ))

    def gtk_show_shortcuts(self):
        LOGGER.info("Showing shortcuts")
        self.widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.shortcutswin", "shortcutswin.glade"
        )
        section = self.widget_tree.get_object("shortcuts_mainwindow")
        window = self.widget_tree.get_object("shortcuts")

        groups = {}
        for shortcut_group in sorted(list(self.groups.keys())):
            group = Gtk.ShortcutsGroup()
            group.set_property("title", shortcut_group)
            group.set_visible(True)
            groups[shortcut_group] = group
            section.add(group)

        for (shortcut_group, shortcuts) in self.groups.items():
            group = groups[shortcut_group]
            shortcuts = sorted(list(shortcuts))
            for (shortcut_desc, shortcut_keys, actions_name) in shortcuts:
                shortcut = Gtk.ShortcutsShortcut()
                shortcut.set_property("accelerator", shortcut_keys)
                shortcut.set_property("title", shortcut_desc)
                shortcut.set_visible(True)
                group.add(shortcut)

        window.set_transient_for(self.windows[-1])
        window.show_all()

    def gtk_hide_shortcuts(self):
        if self.widget_tree is None:
            return
        window = self.widget_tree.get_object("shortcuts")
        window.destroy()

    def screenshot_snap_all_doc_widgets(self, out_dir):
        if self.widget_tree is None:
            return
        self.core.call_success(
            Screenshot.screenshot_snap_widget, self.widget_tree.get_object("shortcuts"),
            self.core.call_success(Fs.fs_join, out_dir, "shortcuts.png"),
        )
