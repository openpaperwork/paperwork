import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    @classmethod
    def get_interfaces(cls):
        return [
            'gtk_pageview_boxes_all',
            'gtk_pageview_boxes_listener',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'gtk_pageview',
                'defaults': ['paperwork_gtk.mainwindow.docview.pageview'],
            },
            {
                'interface': 'gtk_pageview_boxes',
                'defaults': [
                    'paperwork_gtk.mainwindow.docview.pageview.boxes'
                ],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.visible = False

    def set_all_boxes_visible(self, visible):
        self.visible = visible
        self.core.call_all("pageview_refresh_all")

    def on_page_boxes_loaded(self, page, boxes, spatial_index):
        page.refresh()

    def on_page_draw(self, cairo_ctx, page):
        if not self.visible:
            return

        boxes = self.core.call_success(
            "pageview_get_boxes_by_id", page.doc_id, page.page_idx
        )
        if boxes is None:
            return

        for line_box in boxes:
            for word_box in line_box.word_boxes:
                self.core.call_all(
                    "page_draw_box",
                    cairo_ctx, page, word_box.position,
                    (0.0, 0.0, 1.0), border_width=1
                )
