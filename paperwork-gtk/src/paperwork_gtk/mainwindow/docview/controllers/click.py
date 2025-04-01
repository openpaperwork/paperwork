import logging

import openpaperwork_core

from . import BaseDocViewController


LOGGER = logging.getLogger(__name__)


class ClickController(BaseDocViewController):
    def on_page_activated(self, page):
        super().on_page_activated(page)
        LOGGER.info("User activated page %d", page.page_idx)
        self.plugin.core.call_all("docview_set_layout", "paged")
        self.plugin.core.call_all("doc_goto_page", page.page_idx)

    def docview_set_layout(self, name):
        if name == 'grid':
            return
        self.plugin.docview_switch_controller('click', NoClickController)


class NoClickController(BaseDocViewController):
    def docview_set_layout(self, name):
        if name != 'grid':
            return
        self.plugin.docview_switch_controller('click', ClickController)


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['gtk_docview_controller']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'gtk_docview',
                'defaults': ['paperwork_gtk.mainwindow.docview'],
            },
        ]

    def gtk_docview_get_controllers(self, out: dict, docview):
        out['click'] = ClickController(docview)
