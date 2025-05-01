import gettext

import openpaperwork_core
from openpaperwork_core.interfaces.gui import GuiListener

from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.shortcuts import AppShortcutCollector


class Plugin(openpaperwork_core.PluginBase, GuiListener):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': AppAction,
                'defaults': ['paperwork_gtk.actions.page.edit'],
            },
            {
                'interface': AppShortcutCollector,
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
        ]

    def on_gui_initialized(self):
        self.core.call_all(
            AppShortcutCollector.app_shortcut_add,
            gettext.pgettext("keyboard shortcut categories", "Page"),
            gettext.pgettext("keyboard shortcut names", "Edit"),
            "<Control><Shift>e", "win.page_edit"
        )

    @openpaperwork_core.noop
    def new_mainwindow(self):
        pass
