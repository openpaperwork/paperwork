import openpaperwork_core
from openpaperwork_core.interfaces.gui import GuiListener

from paperwork_gtk import _
from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.shortcuts import AppShortcutCollector


class Plugin(openpaperwork_core.PluginBase, GuiListener):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': AppAction,
                'defaults': ['paperwork_gtk.actions.app.find'],
            },
            {
                'interface': AppShortcutCollector,
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
        ]

    def on_gui_initialized(self):
        self.core.call_all(
            AppShortcutCollector.app_shortcut_add,
            _("Global"), _("Find"),
            "<Control>f", "win.app_find"
        )

        # TODO
        # self.core.call_all(
        #     "app_shortcut_add",
        #     _("Global"), _("Find the next match"),
        #     "<Control>G", "win.app_find_next"
        # )
        # self.core.call_all(
        #     "app_shortcut_add",
        #     _("Global"), _("Find the previous match"),
        #     "<Control><Shift>G", "win.app_find_prev"
        # )

    @openpaperwork_core.noop
    def new_mainwindow(self):
        pass
