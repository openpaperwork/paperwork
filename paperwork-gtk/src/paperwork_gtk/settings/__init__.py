import logging

from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.quit import QuitListener
import openpaperwork_core

from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.gtk_window import GtkWindowListener
from openpaperwork_gtk.interfaces.screenshot import Screenshot
from openpaperwork_gtk.interfaces.screenshot import ScreenshotProvider

from paperwork_gtk.interfaces.settings_dialog import SettingsDialog
from paperwork_gtk.interfaces.settings_dialog import SettingsDialogComponent


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    GtkWindowListener,
    QuitListener,
    ScreenshotProvider,
    SettingsDialog,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Config,
                defaults=['openpaperwork_core.config'],
            ),
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=["openpaperwork_gtk.fs.glib"],
            ),
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
            openpaperwork_core.Dependency(
                interface=Screenshot,
                defaults=['openpaperwork_gtk.screenshots'],
            ),
            openpaperwork_core.Dependency(
                interface=SettingsDialogComponent,
                defaults=[],
                optional=True,
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.active_windows = []
        self.sections = {}
        self.widget_tree = None

    def on_gtk_window_opened(self, window):
        self.active_windows.append(window)

    def on_gtk_window_closed(self, window):
        self.active_windows.remove(window)

    def gtk_open_settings(self, *args, **kwargs):
        self.core.call_success(
            GtkResources.gtk_load_css,
            "paperwork_gtk.settings", "settings.css"
        )

        global_widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.settings", "settings.glade"
        )
        self.widget_tree = global_widget_tree
        self.core.call_all(SettingsDialogComponent.complete_settings, global_widget_tree)
        settings = global_widget_tree.get_object("settings_window")
        settings.set_transient_for(self.active_windows[-1])
        settings.set_modal(True)
        settings.connect("destroy", self._save_settings, global_widget_tree)
        settings.set_visible(True)
        self.core.call_all(GtkWindowListener.on_gtk_window_opened, settings)

    def gtk_close_settings(self):
        if self.widget_tree is not None:
            dialog = self.widget_tree.get_object("settings_window")
            dialog.set_visible(False)
            self.widget_tree = None

    def on_quit(self):
        self.gtk_close_settings()

    def _save_settings(self, window, global_widget_tree):
        LOGGER.info("Settings closed. Saving configuration")
        self.core.call_all(Config.config_save)
        self.core.call_all(GtkWindowListener.on_gtk_window_closed, window)
        self.core.call_all(SettingsDialogComponent.on_settings_closed, global_widget_tree)
        self.widget_tree = None

    def add_setting_to_dialog(
            self, global_widget_tree, title, widgets, extra_widget=None):
        """
        Add a setting or a set of settings to the main screen in the settings
        dialog.
        """
        # We have many setting boxes to add to the settings box.
        # --> we need many copies of the setting box --> we load many times
        # the widget tree
        widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.settings", "settings_section.glade"
        )
        widget_tree.get_object("setting_section_name").set_text(title)

        if extra_widget:
            box = widget_tree.get_object("settings_title_box")
            box.pack_start(extra_widget, expand=False, fill=False, padding=0)

        inner = widget_tree.get_object("setting_box")
        for widget in widgets:
            inner.pack_start(widget, expand=False, fill=True, padding=0)
        global_widget_tree.get_object("settings_box").pack_start(
            widget_tree.get_object("setting_section"),
            expand=False, fill=True, padding=0
        )
        self.sections[title] = widget_tree.get_object("setting_section")
        return True

    def add_setting_screen(
            self, global_widget_tree, name, widget_header, widget_body):
        global_widget_tree.get_object("settings_stack_header").add_named(
            widget_header, name
        )
        global_widget_tree.get_object("settings_stack_body").add_named(
            widget_body, name
        )

    def show_setting_screen(self, global_widget_tree, name):
        global_widget_tree.get_object(
            "settings_stack_header"
        ).set_visible_child_name(name)
        global_widget_tree.get_object(
            "settings_stack_body"
        ).set_visible_child_name(name)

    def screenshot_snap_all_doc_widgets(self, out_dir):
        if self.widget_tree is None:
            return
        self.core.call_success(
            Screenshot.screenshot_snap_widget,
            self.widget_tree.get_object("settings_window"),
            self.core.call_success(Fs.fs_join, out_dir, "settings.png")
        )
        for (name, section) in self.sections.items():
            name = name.lower().replace(" ", "_")
            self.core.call_success(
                Screenshot.screenshot_snap_widget, section,
                self.core.call_success(
                    Fs.fs_join, out_dir, "settings_{}.png".format(name)
                ),
                margins=(100, 100, 100, 100)
            )

    def settings_scroll_to_top(self):
        scroll = self.widget_tree.get_object("settings_scrolled_window")
        vadj = scroll.get_vadjustment()
        vadj.set_value(vadj.get_lower())

    def settings_scroll_to_bottom(self):
        scroll = self.widget_tree.get_object("settings_scrolled_window")
        vadj = scroll.get_vadjustment()
        vadj.set_value(vadj.get_upper())
