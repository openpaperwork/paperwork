import logging

import openpaperwork_core

from . import BaseDocViewController


LOGGER = logging.getLogger(__name__)


class PageNumberController(BaseDocViewController):
    def _get_closest_widget(self):
        vadj = self.plugin.scroll.get_vadjustment()
        view_width = self.plugin.scroll.get_allocated_width()
        view_height = self.plugin.scroll.get_allocated_height()
        center = (
            view_width / 2,
            vadj.get_value() + (view_height / 2)
        )

        # look if the center is precisely on in a widget
        for widget in self.plugin.page_layout.get_children():
            if not widget.get_visible():
                continue
            alloc = widget.get_allocation()
            if alloc.width < 10 or alloc.height < 10:
                continue
            if (alloc.x <= center[0] and alloc.y <= center[1] and
                    alloc.x + alloc.width >= center[0] and
                    alloc.y + alloc.height >= center[1]):
                return widget

        # else look for the closest widget
        min_dist = (99999999999999999, None)
        for widget in self.plugin.page_layout.get_children():
            if not widget.get_visible():
                continue
            alloc = widget.get_allocation()
            if alloc.width < 10 or alloc.height < 10:
                continue
            widget_center = (
                (alloc.x + (alloc.width / 2)),
                (alloc.y + (alloc.height / 2)),
            )
            dist_w = (center[0] - widget_center[0])
            dist_h = (center[1] - widget_center[1])
            dist = (dist_w * dist_w) + (dist_h * dist_h)
            if dist < min_dist[0]:
                min_dist = (dist, widget)
        return min_dist[1]

    def _update_current_page(self):
        widget = self._get_closest_widget()
        if widget is None:
            return
        page = self.plugin.widget_to_page[widget]
        self.plugin.core.call_all("on_page_shown", page.page_idx)

    def on_layout_size_allocate(self, layout):
        super().on_layout_size_allocate(layout)
        self._update_current_page()

    def on_page_size_obtained(self, layout):
        super().on_page_size_obtained(layout)
        self._update_current_page()

    def on_vscroll_changed(self, vadj):
        super().on_vscroll_changed(vadj)
        self._update_current_page()

    def on_vscroll_value_changed(self, vadj):
        super().on_vscroll_value_changed(vadj)
        self._update_current_page()


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
        out['page_number'] = PageNumberController(docview)
