import logging

import openpaperwork_core
import openpaperwork_core.deps

from .. import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -1000

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
                'interface': 'stats_post',
                'defaults': ['openpaperwork_core.beacon.stats'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def complete_settings(self, global_widget_tree):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree", "paperwork_gtk.settings", "stats.glade"
        )

        active = self.core.call_success("config_get", "send_statistics")
        LOGGER.info("Statistics state: %s", active)

        button = widget_tree.get_object("stats_state")
        button.set_active(active)
        button.connect("notify::active", self._on_stats_state_changed)

        button = widget_tree.get_object("stats_infos")
        details = widget_tree.get_object("stats_details")
        button.connect("clicked", self._on_info_button, details)

        self.core.call_success(
            "add_setting_to_dialog", global_widget_tree,
            _("Help Improve Paperwork"),
            [widget_tree.get_object("stats")]
        )

    def _on_info_button(self, info_button, details):
        details.set_visible(not details.get_visible())

    def _on_stats_state_changed(self, switch, _):
        state = switch.get_active()
        LOGGER.info("Setting stats state to %s", state)
        self.core.call_all("config_put", "send_statistics", state)
