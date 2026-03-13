"""
When drag'n'dropping, enables the dropping-in-a-document part.
"""

import logging

import openpaperwork_core

from paperwork_gtk.interfaces.doc_viewer import (
    DocViewerControllerFactory,
    DocViewerListener
)
from paperwork_gtk.interfaces.drag_n_drop import DragAndDrop
from paperwork_gtk.mainwindow.docview.controllers import BaseDocViewController


LOGGER = logging.getLogger(__name__)


class DropController(BaseDocViewController):
    LINE_BORDERS = 10
    LINE_WIDTH = 3
    LINE_COLOR = (0.0, 0.8, 1.0, 1.0)

    def __init__(self, core, plugin):
        super().__init__(core, plugin)
        self.closest = None
        self.beforeafter = -1  # 0 for before the widget, 1 for after

    @staticmethod
    def _compute_squared_distance(rect, x, y):
        pts = (
            (rect.x, rect.y),
            (rect.x + rect.width, rect.y),
            (rect.x, rect.y + rect.height),
            (rect.x + rect.width, rect.y + rect.height),
        )
        dists = {
            ((abs(pt[0] - x) ** 2) + (abs(pt[1] - y) ** 2))
            for pt in pts
        }
        return min(dists)

    def _compute_closest(self, x, y):
        dists = {
            (
                self._compute_squared_distance(widget.get_allocation(), x, y),
                widget
            )
            for widget in self.plugin.page_layout.get_children()
        }
        try:
            return min(dists)[1]
        except ValueError:
            # empty list of widgets
            return None

    @staticmethod
    def _compute_beforeafter(rect, x, y):
        center = rect.x + (rect.width / 2)
        return 0 if x < center else 1

    def on_drag_motion(self, drag_context, x, y, time):
        super().on_drag_motion(drag_context, x, y, time)

        self.closest = self._compute_closest(x, y)
        if self.closest is None:
            self.beforeafter = -1
            return

        self.beforeafter = self._compute_beforeafter(
            self.closest.get_allocation(), x, y
        )

        self.plugin.page_layout.queue_draw()

    def on_drag_leave(self, drag_context, time):
        super().on_drag_leave(drag_context, time)
        self.closest = None
        self.plugin.page_layout.queue_draw()

    def on_draw(self, cairo_ctx):
        super().on_draw(cairo_ctx)

        if self.closest is None:
            return

        allocation = self.closest.get_allocation()
        height = allocation.height
        x = allocation.x
        x -= 2 * self.LINE_BORDERS
        x += (self.beforeafter * (allocation.width + 2 * self.LINE_BORDERS))
        x = max(0, x)
        y = allocation.y

        cairo_ctx.save()
        try:
            cairo_ctx.set_source_rgba(*self.LINE_COLOR)
            cairo_ctx.set_line_width(self.LINE_WIDTH)

            cairo_ctx.move_to(x + self.LINE_BORDERS, y)
            cairo_ctx.line_to(x + self.LINE_BORDERS, y + height)
            cairo_ctx.stroke()

            cairo_ctx.move_to(x, y + self.LINE_BORDERS)
            cairo_ctx.line_to(
                x + (2 * self.LINE_BORDERS),
                y + self.LINE_BORDERS
            )
            cairo_ctx.stroke()

            cairo_ctx.move_to(x, y + height - self.LINE_BORDERS)
            cairo_ctx.line_to(
                x + (2 * self.LINE_BORDERS),
                y + height - self.LINE_BORDERS
            )
            cairo_ctx.stroke()
        finally:
            cairo_ctx.restore()

    def drag_and_drop_get_destination(self, x, y):
        super().drag_and_drop_get_destination(x, y)
        closest = self._compute_closest(x, y)
        if closest is None:
            dst_page_idx = 0
        else:
            page = self.plugin.widget_to_page[closest]
            beforeafter = self._compute_beforeafter(
                closest.get_allocation(), x, y
            )
            dst_page_idx = page.page_idx + beforeafter
        return (*self.plugin.active_doc, dst_page_idx)


class Plugin(
    openpaperwork_core.PluginBase,
    DocViewerControllerFactory,
    DocViewerListener,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=DragAndDrop,
                defaults=['paperwork_gtk.gesture.drag_and_drop'],
            ),
        ]

    def on_gtk_docview_init(self, docview):
        self.core.call_all(DragAndDrop.drag_and_drop_page_enable, docview.page_layout)

    @openpaperwork_core.noop
    def on_layout_change(self, layout):
        pass

    def gtk_docview_get_controllers(self, out: dict, docview):
        out['drop'] = DropController(self.core, docview)

    @openpaperwork_core.noop
    def on_docview_closed_page(self, page):
        pass

    @openpaperwork_core.noop
    def on_docview_zoom_updated(self, zoom):
        pass
