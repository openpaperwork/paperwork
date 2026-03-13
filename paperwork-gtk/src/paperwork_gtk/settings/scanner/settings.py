import logging

import openpaperwork_core
from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.l10n import L10nInit
from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.screenshot import Screenshot, ScreenshotProvider
from paperwork_backend.interfaces.scan import Scan

from paperwork_gtk import _
from paperwork_gtk.interfaces.settings import GtkSettingsScannerExtra
from paperwork_gtk.interfaces.settings import GtkSettingsScannerSetting
from paperwork_gtk.interfaces.settings_dialog import SettingsDialog
from paperwork_gtk.interfaces.settings_dialog import SettingsDialogComponent


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    SettingsDialogComponent,
    ScreenshotProvider
):
    PRIORITY = -400
    MODES = {
        'Color': _("Color"),
        'Gray': _("Grayscale"),
        'Lineart': _("Black & White"),
    }

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Config,
                defaults=['openpaperwork_core.config'],
            ),
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=['openpaperwork_gtk.fs.gio'],
            ),
            openpaperwork_core.Dependency(
                interface=GtkSettingsScannerExtra,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=GtkSettingsScannerSetting,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=L10nInit,
                defaults=['paperwork_gtk.l10n'],
            ),
            openpaperwork_core.Dependency(
                interface=Scan,
                defaults=['paperwork_backend.docscan.libinsane'],
            ),
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
            openpaperwork_core.Dependency(
                interface=SettingsDialog,
                defaults=[],
            ),
            openpaperwork_core.Dependency(
                interface=Screenshot,
                defaults=['openpaperwork_gtk.screenshots'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)

        self.widget_tree = None
        self.extra_widget = None
        self.config = [
            (
                'settings_scanner_name', 'scanner_device_value',
                _("No scanner selected"), "{}".format
            ),
            (
                'scanner_resolution', 'scanner_resolution_value',
                _("No resolution selected"), _("{} dpi").format
            ),
            (
                'scanner_mode', 'scanner_mode_value',
                _("No mode selected"), self._translate_mode
            ),
        ]

        opt = self.core.call_success(
            Config.config_build_simple, "settings_scanner", "name",
            lambda: self.core.call_success(Config.config_get, "scanner_dev_id")
        )
        self.core.call_all(Config.config_register, "settings_scanner_name", opt)
        self.core.call_all(
            Config.config_add_observer, "scanner_dev_id", self._update_scanner_name
        )

    def _update_scanner_name(self):
        def set_scanner_name(devs):
            active = self.core.call_success(Config.config_get, "scanner_dev_id")
            for dev in devs:
                dev_id = dev[0]
                dev_name = dev[1]
                if dev_id == active:
                    self.core.call_success(
                        Config.config_put, "settings_scanner_name", dev_name
                    )
                    break
            return devs

        promise = self.core.call_success(Scan.scan_list_scanners_promise)
        promise = promise.then(set_scanner_name)
        self.core.call_success(Scan.scan_schedule, promise)

    def complete_settings(self, global_widget_tree):
        widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree, "paperwork_gtk.settings.scanner",
            "settings.glade"
        )
        self.widget_tree = widget_tree

        extra_widget = self.core.call_success(
            GtkSettingsScannerExtra.settings_scanner_get_extra_widget
        )

        self.core.call_success(
            SettingsDialog.add_setting_to_dialog, global_widget_tree,
            _("Scanner"),
            [
                widget_tree.get_object("scanner_device"),
                widget_tree.get_object("scanner_resolution"),
                widget_tree.get_object("scanner_mode"),
                widget_tree.get_object("scanner_calibration"),
            ],
            extra_widget=extra_widget
        )

        def refresh(*args, **kwargs):
            self._refresh_settings(widget_tree)

        def disable_refresh(*args, **kwargs):
            for c in self.config:
                self.core.call_all(Config.config_remove_observer, c[0], refresh)

        for c in self.config:
            self.core.call_all(Config.config_add_observer, c[0], refresh)

        global_widget_tree.get_object("settings_window").connect(
            "destroy", disable_refresh
        )

        self._refresh_settings(widget_tree)

        list_scanners_promise = self.core.call_success(
            Scan.scan_list_scanners_promise
        )
        self.core.call_all(
            GtkSettingsScannerSetting.complete_scanner_settings,
            global_widget_tree, widget_tree,
            list_scanners_promise
        )
        self.core.call_success(Scan.scan_schedule, list_scanners_promise)

    def _translate_mode(self, mode):
        if mode in self.MODES:
            return self.MODES[mode]
        return mode

    def _refresh_settings(self, widget_tree):
        for (config_key, widget_name, default_value, fmt) in self.config:
            value = self.core.call_success(Config.config_get, config_key)
            if value is not None:
                value = fmt(value)
            else:
                value = default_value
            widget_tree.get_object(widget_name).set_text(value)

        active = self.core.call_success(Config.config_get, "scanner_dev_id")
        active = active is not None and active != ""
        buttons = [
            'scanner_resolution',
            'scanner_mode',
            'scanner_calibration',
        ]
        for button in buttons:
            # WORKAROUND(Jflesch): set_sensitive() doesn't appear to work on
            # GtkMenuButton
            widget_tree.get_object(button).set_sensitive(active)

    def screenshot_snap_all_doc_widgets(self, out_dir):
        if self.widget_tree is None:
            return

        buttons = [
            "scanner_device",
            "scanner_resolution",
            "scanner_mode",
            "scanner_calibration",
        ]
        for button_name in buttons:
            button = self.widget_tree.get_object(button_name)
            self.core.call_success(
                Screenshot.screenshot_snap_widget, button,
                self.core.call_success(
                    Fs.fs_join, out_dir, "settings_{}.png".format(button_name)
                ),
                margins=(100, 100, 100, 100)
            )

    @openpaperwork_core.noop
    def on_settings_closed(self, settings_dialog_widget_tree):
        pass
