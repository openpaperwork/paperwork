import logging

from paperwork_gtk.interfaces.page_boxes import PageViewBoxes
from paperwork_gtk.interfaces.page_boxes import PageViewBoxesAll
from paperwork_gtk.interfaces.page_boxes import PageViewBoxesListener

import openpaperwork_core

from paperwork_gtk.interfaces.page_drawer import PageDrawer


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    PageDrawer,
    PageViewBoxesAll,
    PageViewBoxesListener,
):
    PRIORITY = 1000

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=PageViewBoxes,
                defaults=['paperwork_gtk.mainwindow.docview.pageview.boxes'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.visible = False

    def set_all_boxes_visible(self, visible):
        self.visible = visible

    def on_page_boxes_loaded(self, page, boxes, spatial_index):
        page.refresh()

    def on_page_draw(self, cairo_ctx, page):
        if not self.visible:
            return

        boxes = self.core.call_success(
            PageViewBoxes.pageview_get_boxes_by_id, page.doc_id, page.page_idx
        )
        if boxes is None:
            return

        for line_box in boxes:
            for word_box in line_box.word_boxes:
                self.core.call_all(
                    PageViewBoxes.page_draw_box,
                    cairo_ctx, page, word_box.position,
                    (0.0, 0.0, 1.0), border_width=1
                )

    @openpaperwork_core.noop
    def pageview_refresh_all(self):
        pass

    @openpaperwork_core.noop
    def on_page_visibility_changed(self, page, visible):
        pass
