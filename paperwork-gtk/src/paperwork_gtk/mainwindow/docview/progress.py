import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return []

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'gtk_progress_widget',
                'defaults': ['openpaperwork_gtk.widgets.progress'],
            },
            {
                'interface': 'gtk_docview',
                'defaults': ['paperwork_gtk.mainwindow.docview'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        widget = self.core.call_success("gtk_progress_make_widget")
        if widget is None:
            # GTK is not available
            return
        header_bar = self.core.call_success("docview_get_headerbar")
        header_bar.pack_end(widget)
