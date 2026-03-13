import logging

from openpaperwork_core.interfaces.config import Config
import openpaperwork_core

from openpaperwork_gtk.interfaces.gtk import GtkResources

from paperwork_gtk import _
from paperwork_gtk.interfaces.settings import GtkSettingsScannerSetting


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase, GtkSettingsScannerSetting):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Config,
                defaults=['openpaperwork_core.config'],
            ),
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
        ]

    def complete_scanner_settings(
            self, global_widget_tree, parent_widget_tree,
            list_scanner_promise):
        widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.settings.scanner",
            "popover.glade"
        )

        widget_tree.get_object("settings_stack").set_visible_child_name(
            "spinner"
        )
        widget_tree.get_object("spinner").start()

        parent_widget_tree.get_object("scanner_device").set_popover(
            widget_tree.get_object("selector")
        )

        list_scanner_promise.then(self._on_scanner_list, widget_tree)

    def _on_scanner_list(self, devs, widget_tree):
        widget_tree.get_object("spinner").stop()
        widget_tree.get_object("settings_stack").set_visible_child_name(
            "selector"
        )
        box = widget_tree.get_object("selector_box")

        radios = []
        # because of the way radio buttons work, we need always at least
        # one choice --> add "no scanner"
        for dev in ([(None, _("No scanner"))] + devs):
            radio = self.core.call_success(
                GtkResources.gtk_load_widget_tree, "paperwork_gtk.settings.scanner",
                "popover_box.glade"
            )
            radio = radio.get_object("radio")
            radio.set_label(dev[1])
            box.pack_start(radio, expand=False, fill=True, padding=0)
            radios.append((dev[0], radio))

        for (dev_id, radio) in radios[1:]:
            radio.join_group(radios[0][1])

        active = self.core.call_success(Config.config_get, "scanner_dev_id")

        for (dev_id, radio) in radios:
            if active == dev_id:
                radio.set_active(True)
                break

        for (dev_id, radio) in radios:
            radio.connect(
                "toggled", self._on_toggle,
                widget_tree, dev_id, radio.get_label()
            )

    def _on_toggle(
            self, checkbox, widget_tree, dev_id, dev_name):
        LOGGER.info("Selected scanner: %s - %s", dev_id, dev_name)
        widget_tree.get_object("selector").popdown()
        self.core.call_success(Config.config_put, "scanner_dev_id", dev_id)
