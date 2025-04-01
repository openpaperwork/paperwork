import logging

import openpaperwork_core

from . import BaseDocViewController


LOGGER = logging.getLogger(__name__)


class BaseLayoutController(BaseDocViewController):
    def __init__(self, plugin):
        super().__init__(plugin)
        self.core = plugin.core
        self.real_nb_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", self.plugin.active_doc[1]
        )
        if self.real_nb_pages is None:
            self.real_nb_pages = 0

    def on_close(self):
        for page in self.plugin.page_layout.get_children():

            # weird but has to be done. Otherwise it seems the children
            # are destroyed with 'page'
            for c in page.get_children():
                page.remove(c)

            self.plugin.page_layout.remove(page)
        self.plugin.pages = []
        self.plugin.widget_to_page = {}
        self.plugin.page_to_widget = {}

    def _update_visibility(self):
        vadj = self.plugin.scroll.get_vadjustment()
        lower = vadj.get_lower()
        p_min = vadj.get_value() - lower
        p_max = vadj.get_value() + vadj.get_page_size() - lower
        for widget in self.plugin.page_layout.get_children():
            alloc = widget.get_allocation()
            p_lower = alloc.y
            p_upper = alloc.y + alloc.height
            visible = (p_min <= p_upper and p_lower <= p_max)
            page = self.plugin.widget_to_page[widget]
            page.set_visible(visible)

    def on_vscroll_value_changed(self, vadj):
        super().on_vscroll_value_changed(vadj)
        self._update_visibility()

    def on_vscroll_changed(self, vadj):
        super().on_vscroll_changed(vadj)
        self._update_visibility()

    def on_page_size_obtained(self, page):
        super().on_page_size_obtained(page)
        self._update_visibility()

    def on_layout_size_allocate(self, layout):
        super().on_layout_size_allocate(layout)
        self._update_visibility()

    def _add_pages(self):
        pages = []
        self.core.call_all(
            "doc_open_components", pages, *self.plugin.active_doc
        )
        for (visible, page) in pages:
            self.plugin.docview_add_page_viewer(page, visible)

    def doc_reload(self):
        super().doc_reload()
        LOGGER.info("Reloading document %s", self.plugin.active_doc)
        self.on_close()
        self._add_pages()
        for page in self.plugin.pages:
            page.load()


class LayoutControllerLoading(BaseLayoutController):
    def __init__(self, plugin):
        super().__init__(plugin)
        self.nb_loaded = 0

        # page instantiation must be done before the calls to enter()
        # because other controllers may need the pages. So we cheat a little
        # bit and make it in the constructor.
        self._add_pages()

    def enter(self):
        super().enter()
        if len(self.plugin.pages) <= 0:
            self.plugin.docview_switch_controller(
                'layout', LayoutControllerLoaded
            )
            return
        self.nb_loaded = 0
        for page in self.plugin.pages:
            page.load()

    def on_page_size_obtained(self, page):
        super().on_page_size_obtained(page)
        self.nb_loaded += 1
        if self.nb_loaded >= len(self.plugin.pages):
            self.plugin.docview_switch_controller(
                'layout', LayoutControllerLoaded
            )

    def exit(self):
        LOGGER.info(
            "Size of all pages of doc %s loaded", self.plugin.active_doc[0]
        )


class LayoutControllerLoaded(BaseLayoutController):
    def enter(self):
        super().enter()
        self._update_visibility()


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
        out['layout'] = LayoutControllerLoading(docview)
