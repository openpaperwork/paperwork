import openpaperwork_core

from .... import _
from . import BaseDocViewController


class TitleController(BaseDocViewController):
    def enter(self):
        folded = self.plugin.core.call_success("mainwindow_get_folded")
        if folded:
            self.plugin.widget_tree.get_object(
                "docview_header"
            ).set_title("")
            return

        (doc_id, doc_url) = self.plugin.active_doc
        if self.plugin.core.call_success("is_doc", doc_url) is not None:
            doc_date = self.plugin.core.call_success(
                "doc_get_date_by_id", doc_id
            )
            if doc_date is not None:
                doc_date = self.plugin.core.call_success(
                    "i18n_date_short", doc_date
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


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['gtk_docview_controller']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_docview',
                'defaults': ['paperwork_gtk.mainwindow.docview'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.controller = None

    def gtk_docview_get_controllers(self, out: dict, docview):
        self.controller = TitleController(docview)
        out['title'] = self.controller

    def on_mainwindow_fold_change(self):
        if self.controller is None:
            return
        # update the title bar
        self.controller.enter()
