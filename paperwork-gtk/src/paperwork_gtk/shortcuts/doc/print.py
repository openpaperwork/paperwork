import openpaperwork_core

from openpaperwork_core.interfaces.gui import GuiListener

from paperwork_gtk import _
from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.shortcuts import AppShortcutCollector


class Plugin(openpaperwork_core.PluginBase, GuiListener):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=AppAction,
                defaults=['paperwork_gtk.actions.doc.print'],
            ),
            openpaperwork_core.Dependency(
                interface=AppShortcutCollector,
                defaults=['paperwork_gtk.mainwindow.window'],
            ),
        ]

    def on_gui_initialized(self):
        self.core.call_all(
            AppShortcutCollector.app_shortcut_add,
            _("Document"), _("Print"),
            "<Control>P", "win.doc_print"
        )

    @openpaperwork_core.noop
    def new_mainwindow(self):
        pass
