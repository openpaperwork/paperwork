import logging

import openpaperwork_core

from . import BaseDocViewController


LOGGER = logging.getLogger(__name__)


class ZoomLayoutController(BaseDocViewController):
    def __init__(self, plugin):
        super().__init__(plugin)
        self.last_zoom = -1

    def _recompute_zoom(self):
        layout_name = self.plugin.layout_name
        spacing = self.plugin.page_layout.get_column_spacing()
        nb_columns = self.plugin.LAYOUTS[layout_name]
        max_columns = 0
        view_width = self.plugin.scroll.get_allocated_width()
        zoom = 1.0
        for page_idx in range(0, len(self.plugin.pages), nb_columns):
            pages = self.plugin.pages[page_idx:page_idx + nb_columns]
            pages_width = sum([p.get_full_size()[0] for p in pages])
            pages_width += (len(pages) * 30 * spacing) + 1
            zoom = min(zoom, view_width / pages_width)
            max_columns = max(max_columns, len(pages))

        if zoom == self.last_zoom:
            return
        self.last_zoom = zoom

        self.plugin.core.call_all("docview_set_zoom", zoom)
        for page in self.plugin.pages:
            page.set_zoom(zoom)

        if nb_columns > 1:
            layout = 'grid'
        else:
            layout = 'paged'
        self.plugin.core.call_all("on_layout_change", layout)

    def enter(self):
        super().enter()
        self._recompute_zoom()

    def docview_set_zoom(self, zoom):
        super().docview_set_zoom(zoom)
        if zoom == self.last_zoom:
            return
        self.plugin.docview_switch_controller('zoom', ZoomCustomController)

    def docview_set_layout(self, name):
        super().docview_set_layout(name)
        self._recompute_zoom()

    def on_page_size_obtained(self, page):
        super().on_page_size_obtained(page)
        self._recompute_zoom()

    def on_layout_size_allocate(self, layout):
        self._recompute_zoom()

    def doc_reload(self):
        self._recompute_zoom()


class ZoomCustomController(BaseDocViewController):
    def _reapply_zoom(self):
        zoom = self.plugin.zoom
        for page in self.plugin.pages:
            page.set_zoom(zoom)

    def enter(self):
        super().enter()
        self._reapply_zoom()

    def docview_set_zoom(self, zoom):
        super().docview_set_zoom(zoom)
        self._reapply_zoom()

    def docview_set_layout(self, name):
        super().docview_set_layout(name)
        self.plugin.docview_switch_controller('zoom', ZoomLayoutController)


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
        out['zoom'] = ZoomLayoutController(docview)
