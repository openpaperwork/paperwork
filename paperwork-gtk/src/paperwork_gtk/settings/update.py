import logging

import openpaperwork_core
import openpaperwork_core.deps

from .. import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -750

    @classmethod
    def get_interfaces(cls):
        return [
            'gtk_settings',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'update_detection',
                'defaults': ['paperwork_backend.beacon.update'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def complete_settings(self, global_widget_tree):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree", "paperwork_gtk.settings", "update.glade"
        )

        active = self.core.call_success("config_get", "check_for_update")
        LOGGER.info("Updates check: %s", active)

        button = widget_tree.get_object("updates_state")
        button.set_active(active)
        button.connect("notify::active", self._on_updates_state_changed)

        button = widget_tree.get_object("updates_infos")
        details = widget_tree.get_object("updates_details")
        button.connect("clicked", self._on_info_button, details)

        self.core.call_success(
            "add_setting_to_dialog", global_widget_tree,
            _("Updates"),
            [widget_tree.get_object("updates")]
        )

    def _on_info_button(self, info_button, details):
        details.set_visible(not details.get_visible())

    def _on_updates_state_changed(self, switch, _):
        state = switch.get_active()
        LOGGER.info("Setting update check state to %s", state)
        self.core.call_all("config_put", "check_for_update", state)
