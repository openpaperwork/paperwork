import logging

try:
    import gi
    gi.require_version('Pango', '1.0')
    gi.require_version('PangoCairo', '1.0')
    from gi.repository import Pango
    from gi.repository import PangoCairo
    PANGO_AVAILABLE = True
except (ImportError, ValueError):
    PANGO_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.progress import ProgressListener
from openpaperwork_core.interfaces.spatial_index import SpatialIndex
from openpaperwork_core.interfaces.work_queue import WorkQueue
import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise

from paperwork_backend.interfaces.docs import DocOpener
from paperwork_backend.interfaces.pages import PageText

from paperwork_gtk.interfaces.page_boxes import PageViewBoxes
from paperwork_gtk.interfaces.page_boxes import PageViewBoxesListener
from paperwork_gtk.interfaces.page_drawer import PageDrawer
from paperwork_gtk import _


LOGGER = logging.getLogger(__name__)
DELAY = 0.1


class NBox:
    """
    Chained boxes. Useful for some plugins like boxes.selection.
    """
    def __init__(self, box, index):
        self.box = box
        self.next = None
        self.index = index

    def __lt__(self, other):
        if self.index < other.index:
            return True
        return (self.box.position < other.box.position)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    DocOpener,
    PageDrawer,
    PageViewBoxes,
    PageViewBoxesListener,
):
    """
    Load the boxes on the pages and notify them to other plugins.
    Do nothing else. See other plugins in
    paperwork_gtk.mainwindow.docview.pageview.boxes to have something actually
    happening.
    """

    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            {
                "interface": PageText,
                "defaults": [],
                "optional": True,
            },
            {
                "interface": ProgressListener,
                "defaults": [],
                "optional": True,
            },
            {
                'interface': SpatialIndex,
                'defaults': ['openpaperwork_core.spatial.rtree'],
            },
            {
                'interface': WorkQueue,
                'defaults': ['openpaperwork_core.work_queue.default'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.cache = {}
        self.running_promises = {}
        self.nb_to_load = 0
        self.nb_loaded = 0

    def chkdeps(self, out: dict):
        if not PANGO_AVAILABLE:
            out['pango'].update(openpaperwork_core.deps.PANGO)

    def _upd_progress(self):
        if self.nb_to_load <= self.nb_loaded or self.nb_to_load == 0:
            self.core.call_all(ProgressListener.on_progress, "boxes", 1.0)
            self.nb_to_load = 0
            self.nb_loaded = 0
            return
        self.core.call_all(
            ProgressListener.on_progress, "boxes",
            self.nb_loaded / self.nb_to_load, _("Loading text ...")
        )

    def doc_close(self):
        self.cache = {}
        self.nb_to_load = 0
        self.nb_loaded = 0
        self._upd_progress()

    def doc_open(self, *args, **kwargs):
        self.doc_close()

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    def _index_boxes(self, boxes):
        # Tesseract seems (seemed ?) to have a bug: boxes taking the whole
        # page. --> we remove them.
        # Also we strip empty boxes.
        boxes = [
            line_box for line_box in boxes
            if line_box.position[0][0] > 0 or line_box.position[0][1] > 0
        ]
        for line_box in boxes:
            line_box.word_boxes = [
                word_box for word_box in line_box.word_boxes
                if ((word_box.position[0][0] > 0 or
                    word_box.position[0][1] > 0) and
                    word_box.content.strip() != "")
            ]

        # chain the boxes
        chained_boxes = []
        pbox = None
        index = 0
        for line in boxes:
            for word in line.word_boxes:
                new_box = NBox(word, index)
                index += 1
                if pbox is not None:
                    pbox.next = new_box
                    chained_boxes.append(pbox)
                pbox = new_box
        if pbox is not None:
            chained_boxes.append(pbox)

        # and then index them
        spatial_index = self.core.call_success(
            SpatialIndex.spatial_indexer_get, [
                (b.box.position, b)
                for b in chained_boxes
            ]
        )

        return (boxes, spatial_index)

    def _set_boxes(self, boxes, page):
        (boxes, spatial_index) = boxes
        ref = (page.doc_id, page.page_idx)
        self.cache[ref] = (boxes, spatial_index)
        return (boxes, spatial_index)

    def pageview_get_boxes_by_id(self, doc_id, page_idx):
        ref = (doc_id, page_idx)
        if ref not in self.cache:
            return None
        return self.cache[ref][0]

    def on_page_visibility_changed(self, page, visible):
        ref = (page.doc_id, page.page_idx)
        if not visible:
            promise = self.running_promises.pop(ref, None)
            if promise is not None:
                self.core.call_all(WorkQueue.work_queue_cancel, "page_loader", promise)
                self.nb_to_load -= 1
                self._upd_progress()
            if ref in self.cache:
                self.cache.pop(ref)
            return

        if ref in self.cache:
            return

        # even they are not yet loaded, they will soon be --> we can mark them
        # as loaded
        self.cache[ref] = (None, None)

        # Gives back a bit of CPU time to GTK so the GUI remains
        # usable
        promise = openpaperwork_core.promise.DelayPromise(self.core, DELAY)

        promise = promise.then(
            LOGGER.debug,
            "Loading boxes of %s p%d", page.doc_id, page.page_idx
        )
        # drop the returned value
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, self.core.call_success,
            args=(PageText.page_get_boxes_by_url, page.doc_url, page.page_idx,)
        ))
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, lambda boxes=[]: self._index_boxes(boxes)
        ))
        promise = promise.then(lambda boxes: self._set_boxes(boxes, page))
        promise = promise.then(lambda boxes: self.core.call_all(
            # boxes => (boxes, spatial_index)
            PageViewBoxesListener.on_page_boxes_loaded, page, boxes[0], boxes[1]
        ))

        def stop_promise_tracking(*args, **kwargs):
            if ref in self.running_promises:
                self.nb_loaded += 1
                self._upd_progress()
                self.running_promises.pop(ref)

        promise = promise.then(stop_promise_tracking)

        self.nb_to_load += 1
        self._upd_progress()
        self.running_promises[ref] = promise

        # piggy back page loader work queue, but with a low priority
        self.core.call_success(
            WorkQueue.work_queue_add_promise, "page_loader", promise, priority=-10
        )

    def on_page_boxes_loaded(self, page, boxes, spatial_index):
        LOGGER.info(
            "Page %s %d: %d line boxes loaded",
            page.doc_id, page.page_idx, len(boxes)
        )

    def _paint_txt(self, cairo_ctx, txt, x, y, w, h):
        cairo_ctx.set_source_rgb(1.0, 1.0, 1.0)
        cairo_ctx.rectangle(x, y, w, h)
        cairo_ctx.fill()

        layout = PangoCairo.create_layout(cairo_ctx)
        layout.set_text(txt, -1)
        txt_size = layout.get_size()
        if 0 in txt_size:
            return

        cairo_ctx.save()
        try:
            txt_factor = min(
                float(w) * Pango.SCALE / txt_size[0],
                float(h) * Pango.SCALE / txt_size[1],
            )
            cairo_ctx.set_source_rgb(0, 0, 0)
            cairo_ctx.translate(x, y)

            # make the text use the whole box space
            cairo_ctx.scale(txt_factor, txt_factor)

            PangoCairo.update_layout(cairo_ctx, layout)
            PangoCairo.show_layout(cairo_ctx, layout)
        finally:
            cairo_ctx.restore()

    def _page_draw_box(
            self, cairo_ctx, page, box_position,
            border_color, border_width=2,
            box_content=None):
        zoom = page.zoom
        ((tl_x, tl_y), (br_x, br_y)) = box_position
        tl_x *= zoom
        tl_y *= zoom
        br_x *= zoom
        br_y *= zoom
        w = br_x - tl_x
        h = br_y - tl_y

        if box_content is not None:
            self._paint_txt(cairo_ctx, box_content, tl_x, tl_y, w, h)

        cairo_ctx.save()
        try:

            cairo_ctx.set_source_rgb(
                border_color[0], border_color[1], border_color[2]
            )
            cairo_ctx.set_line_width(border_width)
            cairo_ctx.rectangle(
                tl_x - (border_width / 2),
                tl_y - (border_width / 2),
                w + border_width,
                h + border_width
            )
            cairo_ctx.stroke()
        finally:
            cairo_ctx.restore()

    def page_draw_box(self, *args, **kwargs):
        # WORKAROUND(Jflesch): with some malformed PDF file, we get unexpected
        # exceptions. See:
        # https://gitlab.gnome.org/World/OpenPaperwork/paperwork/-/issues/913
        # https://gitlab.freedesktop.org/poppler/poppler/-/issues/1020
        try:
            self._page_draw_box(*args, **kwargs)
        except Exception as exc:
            LOGGER.error("page_draw_box() failed", exc_info=exc)

    @openpaperwork_core.noop
    def pageview_refresh_all(self):
        pass

    @openpaperwork_core.noop
    def on_page_draw(self, cairo_ctx, page):
        pass
