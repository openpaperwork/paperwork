import openpaperwork_core

from ... import _


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'shortcuts',
            'shortcuts_doc',
            'shortcuts_doc_copy_text',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'action_doc_new',
                'defaults': ['paperwork_gtk.actions.doc.new'],
            },
            {
                'interface': 'app_shortcuts',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
        ]

    def on_gtk_initialized(self):
        self.core.call_all(
            "app_shortcut_add",
            _("Global"), _("Create new document"),
            "<Control>N", "win.doc_new"
        )
