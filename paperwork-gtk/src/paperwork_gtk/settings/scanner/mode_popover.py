import logging

from openpaperwork_core.interfaces.config import Config
import openpaperwork_core

from openpaperwork_gtk.interfaces.gtk import GtkResources

from paperwork_backend.interfaces.scan import Scan

from paperwork_gtk.interfaces.settings import GtkSettingsScannerSetting


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase, GtkSettingsScannerSetting):
    RECOMMENDED = 300
    MODES = [
        ('radioColor', 'Color'),
        ('radioGrayscale', 'Gray'),
        ('radioLineart', 'Lineart'),
    ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': Config,
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': GtkResources,
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': Scan,
                'defaults': ['paperwork_backend.docscan.libinsane'],
            },
        ]

    def complete_scanner_settings(
            self, global_widget_tree, parent_widget_tree,
            list_scanner_promise):
        widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.settings.scanner",
            "popover_mode.glade"
        )

        active = self.core.call_success(Config.config_get, "scanner_mode")
        for (widget, mode) in self.MODES:
            if mode == active:
                widget_tree.get_object(widget).set_active(True)

        for (widget, mode) in self.MODES:
            widget_tree.get_object(widget).connect(
                "toggled", self._on_toggle,
                widget_tree, mode
            )

        selector = widget_tree.get_object("selector")

        # WORKAROUND(Jflesch): set_sensitive() doesn't appear to work on
        # GtkMenuButton --> we have to play with set_popover()

        def reset_popover():
            dev_id = self.core.call_success(Config.config_get, "scanner_dev_id")
            parent_widget_tree.get_object("scanner_mode").set_popover(
                selector if dev_id is not None and dev_id != "" else None
            )

        reset_popover()
        self.core.call_all(
            Config.config_add_observer, "scanner_dev_id", reset_popover
        )

    def _on_toggle(self, checkbox, widget_tree, mode):
        LOGGER.info("Selected mode: %s", mode)
        widget_tree.get_object("selector").popdown()
        self.core.call_success(Config.config_put, "scanner_mode", mode)
