import logging

import openpaperwork_core

from . import BaseDocViewController


LOGGER = logging.getLogger(__name__)


class Scroller(object):
    def __init__(self, controller, widget):
        self.controller = controller
        self.widget = widget
        self.allocate_handler_id = None

    def goto(self):
        alloc = self.widget.get_allocation()
        if alloc.y < 0:
            self.allocate_handler_id = self.widget.connect(
                "size-allocate", self._goto_on_allocate
            )
        else:
            self._goto_on_allocate()

    def _goto_on_allocate(self, *args, **kwargs):
        alloc = self.widget.get_allocation()
        assert alloc.y >= 0
        self.controller.last_value = alloc.y
        self.controller.plugin.scroll.get_vadjustment().set_value(alloc.y)
        if self.allocate_handler_id is not None:
            self.widget.disconnect(self.allocate_handler_id)
            self.allocate_handler_id = None


class ScrollPageLockedController(BaseDocViewController):
    def __init__(self, plugin):
        super().__init__(plugin)
        self.last_upper = -1
        self.last_value = -1

    def enter(self):
        self.last_value = self.plugin.scroll.get_vadjustment().get_value()
        self.last_upper = self.plugin.scroll.get_vadjustment().get_upper()
        self.doc_goto_page(self.plugin.requested_page_idx)

    def doc_goto_page(self, page_idx):
        super().doc_goto_page(page_idx)
        for widget in self.plugin.page_layout.get_children():
            page = self.plugin.widget_to_page[widget]
            if page.page_idx != page_idx:
                continue
            Scroller(self, widget).goto()

    def on_page_size_obtained(self, page):
        super().on_page_size_obtained(page)
        self.doc_goto_page(self.plugin.requested_page_idx)

    def on_layout_size_allocate(self, layout):
        super().on_layout_size_allocate(layout)
        self.doc_goto_page(self.plugin.requested_page_idx)

    def docview_set_layout(self, name):
        super().docview_set_layout(name)
        self.doc_goto_page(self.plugin.requested_page_idx)

    def docview_set_zoom(self, zoom):
        super().docview_set_zoom(zoom)
        self.doc_goto_page(self.plugin.requested_page_idx)

    def docview_reload_page(self, page_idx):
        super().docview_reload_page(page_idx)
        self.doc_goto_page(self.plugin.requested_page_idx)

    def on_vscroll_changed(self, adj):
        super().on_vscroll_changed(adj)
        if adj.get_upper() == self.last_upper:
            return
        self.last_upper = adj.get_upper()
        self.doc_goto_page(self.plugin.requested_page_idx)

    def on_vscroll_value_changed(self, adj):
        super().on_vscroll_value_changed(adj)
        if adj.get_value() == self.last_value:
            return
        self.last_value = adj.get_value()
        self.plugin.docview_switch_controller('scroll', ScrollFreeController)


class ScrollFreeController(BaseDocViewController):
    def __init__(self, plugin):
        super().__init__(plugin)
        self.scroll_proportion = None

    def _upd_proportion(self):
        vadj = self.plugin.scroll.get_vadjustment()
        self.scroll_proportion = vadj.get_value() / vadj.get_upper()

    def enter(self):
        self._upd_proportion()

    def doc_goto_page(self, page_idx):
        self.plugin.docview_switch_controller(
            'scroll', ScrollPageLockedController
        )

    def _on_vscroll(self, adj):
        if self.scroll_proportion is None:
            return
        pos = self.scroll_proportion * adj.get_upper()
        self.scroll_proportion = None
        adj.set_value(pos)

    def docview_set_zoom(self, zoom):
        self._upd_proportion()

    def docview_set_layout(self, name):
        self._upd_proportion()

    def on_vscroll_changed(self, adj):
        super().on_vscroll_changed(adj)
        self._on_vscroll(adj)

    def on_vscroll_value_changed(self, adj):
        super().on_vscroll_value_changed(adj)
        self._on_vscroll(adj)


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
        out['scroll'] = ScrollPageLockedController(docview)
