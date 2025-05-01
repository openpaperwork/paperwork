import openpaperwork_core
from openpaperwork_core.interfaces.i18n import I18n

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.docs import DocType

from paperwork_gtk import _
from paperwork_gtk.interfaces.doc_viewer import DocViewerControllerFactory
from paperwork_gtk.interfaces.main_window import MainWindow
from paperwork_gtk.interfaces.main_window import MainWindowListener
from paperwork_gtk.mainwindow.docview.controllers import BaseDocViewController


class TitleController(BaseDocViewController):
    def enter(self):
        folded = self.core.call_success(MainWindow.mainwindow_get_folded)
        if folded:
            self.plugin.widget_tree.get_object(
                "docview_header"
            ).set_title("")
            return

        (doc_id, doc_url) = self.plugin.active_doc
        if self.core.call_success(DocType.is_doc, doc_url) is not None:
            doc_date = self.core.call_success(
                DocStorage.doc_get_date_by_id, doc_id
            )
            if doc_date is not None:
                doc_date = self.core.call_success(
                    I18n.i18n_date_short, doc_date
                )
            else:
                doc_date = doc_id
            self.plugin.widget_tree.get_object(
                "docview_header"
            ).set_title(doc_date)
        else:
            self.plugin.widget_tree.get_object(
                "docview_header"
            ).set_title(_("New document"))

    def on_close(self):
        self.plugin.widget_tree.get_object("docview_header").set_title("")


class Plugin(
    openpaperwork_core.PluginBase,
    DocViewerControllerFactory,
    MainWindowListener,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': DocStorage,
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                "interface": DocType,
                "defaults": [
                    "paperwork_backend.model.img",
                    "paperwork_backend.model.pdf",
                ],
            },
            {
                'interface': I18n,
                'defaults': ['openpaperwork_core.i18n.python'],
            },
            {
                "interface": MainWindow,
                "defaults": ["paperwork_gtk.mainwindow.window"],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.controller = None

    def gtk_docview_get_controllers(self, out: dict, docview):
        self.controller = TitleController(self.core, docview)
        out['title'] = self.controller

    def on_mainwindow_fold_change(self):
        if self.controller is None:
            return
        # update the title bar
        self.controller.enter()
