import openpaperwork_core

from ... import _


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'shortcuts',
            'shortcuts_doc',
            'shortcuts_doc_properties',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'action_doc_properties',
                'defaults': ['paperwork_gtk.actions.doc.properties'],
            },
            {
                'interface': 'app_shortcuts',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
        ]

    def on_gtk_initialized(self):
        self.core.call_all(
            "app_shortcut_add",
            _("Document"), _("Edit document properties"),
            "<Control>e", "win.doc_properties"
        )
