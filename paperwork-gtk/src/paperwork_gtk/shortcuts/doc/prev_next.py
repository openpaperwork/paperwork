import openpaperwork_core

from ... import _


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'shortcuts',
            'shortcuts_doc',
            'shortcuts_doc_prev_next',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'action_doc_prev_next',
                'defaults': ['paperwork_gtk.actions.doc.prev_next'],
            },
            {
                'interface': 'app_shortcuts',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
        ]

    def on_gtk_initialized(self):
        self.core.call_all(
            "app_shortcut_add",
            _("Document list"), _("Open next document"),
            "<Control>Page_Down", "win.doc_next"
        )
        self.core.call_all(
            "app_shortcut_add",
            _("Document list"), _("Open previous document"),
            "<Control>Page_Up", "win.doc_prev"
        )
