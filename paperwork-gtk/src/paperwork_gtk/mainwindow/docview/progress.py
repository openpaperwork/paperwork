import openpaperwork_core

from openpaperwork_gtk.interfaces.widgets import GtkProgressWidget

from paperwork_gtk.interfaces.doc_viewer import DocViewer
from paperwork_gtk.interfaces.doc_viewer import DocViewProgress


class Plugin(
    openpaperwork_core.PluginBase,
    DocViewProgress,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': GtkProgressWidget,
                'defaults': ['openpaperwork_gtk.widgets.progress'],
            },
            {
                'interface': DocViewer,
                'defaults': ['paperwork_gtk.mainwindow.docview'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        widget = self.core.call_success(GtkProgressWidget.make_widget)
        if widget is None:
            # GTK is not available
            return
        header_bar = self.core.call_success(DocViewer.docview_get_headerbar)
        header_bar.pack_end(widget)
