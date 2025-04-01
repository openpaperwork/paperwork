import openpaperwork_core

from ... import _


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'shortcuts',
            'shortcuts_doc',
            'shortcuts_doc_print',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'action_doc_print',
                'defaults': ['paperwork_gtk.actions.doc.print'],
            },
            {
                'interface': 'app_shortcuts',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
        ]

    def on_gtk_initialized(self):
        self.core.call_all(
            "app_shortcut_add",
            _("Document"), _("Print"),
            "<Control>P", "win.doc_print"
        )
