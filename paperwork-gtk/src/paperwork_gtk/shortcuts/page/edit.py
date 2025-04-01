import gettext

import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'shortcuts',
            'shortcuts_page',
            'shortcuts_page_edit',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'action_page_edit',
                'defaults': ['paperwork_gtk.actions.page.edit'],
            },
            {
                'interface': 'app_shortcuts',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
        ]

    def on_gtk_initialized(self):
        self.core.call_all(
            "app_shortcut_add",
            gettext.pgettext("keyboard shortcut categories", "Page"),
            gettext.pgettext("keyboard shortcut names", "Edit"),
            "<Control><Shift>e", "win.page_edit"
        )
