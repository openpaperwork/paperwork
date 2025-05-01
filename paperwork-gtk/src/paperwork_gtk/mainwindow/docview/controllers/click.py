import logging

import openpaperwork_core

from paperwork_gtk.interfaces.doc_viewer import DocViewer, DocViewerControllerFactory
from paperwork_gtk.mainwindow.docview.controllers import BaseDocViewController


LOGGER = logging.getLogger(__name__)


class ClickController(BaseDocViewController):
    def on_page_activated(self, page):
        super().on_page_activated(page)
        LOGGER.info("User activated page %d", page.page_idx)
        self.core.call_all(DocViewer.docview_set_layout, "paged")
        self.core.call_all(DocViewer.doc_goto_page, page.page_idx)

    def docview_set_layout(self, name):
        if name == 'grid':
            return
        self.plugin.docview_switch_controller(self.core, 'click', NoClickController)


class NoClickController(BaseDocViewController):
    def docview_set_layout(self, name):
        if name != 'grid':
            return
        self.plugin.docview_switch_controller(self.core, 'click', ClickController)


class Plugin(
    openpaperwork_core.PluginBase,
    DocViewerControllerFactory,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': DocViewer,
                'defaults': ['paperwork_gtk.mainwindow.docview'],
            },
        ]

    def gtk_docview_get_controllers(self, out: dict, docview):
        out['click'] = ClickController(self.core, docview)
