#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2014  Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.

import logging

from gi.repository import GLib
from gi.repository import GObject

from paperwork.frontend.util.canvas.animations import Animation
from paperwork.frontend.util.canvas.animations import ScanAnimation
from paperwork.frontend.util.canvas.animations import SpinnerAnimation
from paperwork.frontend.util.canvas.drawers import Drawer
from paperwork.frontend.util.canvas.drawers import RectangleDrawer
from paperwork.frontend.util.canvas.drawers import PillowImageDrawer
from paperwork.frontend.util.canvas.drawers import fit

logger = logging.getLogger(__name__)


class DocScan(object):

    def __init__(self, doc):
        """
        Arguments:
            doc --- if None, new doc
        """
        self.doc = doc


class PageScan(GObject.GObject):
    __gsignals__ = {
        'scanworkflow-inst': (GObject.SignalFlags.RUN_LAST, None,
                              (GObject.TYPE_PYOBJECT, )),
        'done': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self,
                 main_win, multiscan_win, config,
                 resolution, scan_session,
                 line_idx, doc_scan,
                 page_nb, total_pages):
        GObject.GObject.__init__(self)
        self.__main_win = main_win
        self.__multiscan_win = multiscan_win
        self.__config = config
        self.resolution = resolution
        self.__scan_session = scan_session
        self.line_idx = line_idx
        self.doc_scan = doc_scan
        self.page_nb = page_nb
        self.total_pages = total_pages

    def __on_ocr_done(self, img, line_boxes):
        docid = self.__main_win.remove_scan_workflow(self.scan_workflow)
        self.__main_win.add_page(docid, img, line_boxes)
        self.emit("done")

    def __on_error(self, exc):
        logger.error("Scan failed: %s" % str(exc))
        self.__main_win.remove_scan_workflow(self.scan_workflow)
        self.__main_win.show_doc(self.__main_win.doc, force_refresh=True)
        self.__multiscan_win.on_scan_error_cb(self, exc)

    def __make_scan_workflow(self):
        self.scan_workflow = self.__main_win.make_scan_workflow()
        self.scan_workflow.connect("scan-start", lambda _: GLib.idle_add(
            self.__multiscan_win.on_scan_start_cb, self))
        self.scan_workflow.connect("scan-error", lambda _, exc:
                                   GLib.idle_add(self.__on_error, exc))
        self.scan_workflow.connect("ocr-start", lambda _, a: GLib.idle_add(
            self.__multiscan_win.on_ocr_start_cb, self))
        self.scan_workflow.connect("process-done",
                                   lambda _, a, b: GLib.idle_add(
                                       self.__multiscan_win.on_scan_done_cb,
                                       self))
        self.scan_workflow.connect("process-done",
                                   lambda scan_workflow, img, boxes:
                                   GLib.idle_add(self.__on_ocr_done,
                                                 img, boxes))
        self.emit('scanworkflow-inst', self.scan_workflow)

    def start_scan_workflow(self):
        self.__make_scan_workflow()
        if not self.doc_scan.doc:
            self.doc_scan.doc = self.__main_win.doclist.get_new_doc()
        self.__main_win.show_doc(self.doc_scan.doc)
        drawer = self.__main_win.make_scan_workflow_drawer(
            self.scan_workflow, single_angle=False)
        self.__main_win.add_scan_workflow(self.doc_scan.doc, drawer)
        self.scan_workflow.scan_and_ocr(self.resolution, self.__scan_session)

    def connect_next_page_scan(self, next_page_scan):
        self.connect("done", lambda _: GLib.idle_add(
            next_page_scan.start_scan_workflow))


GObject.type_register(PageScan)


class PageScanDrawer(Animation):
    layer = Drawer.IMG_LAYER
    visible = True

    DEFAULT_SIZE = (70, 100)

    def __init__(self, position):
        Animation.__init__(self)
        self.position = position
        self.scan_animation = None
        self.size = self.DEFAULT_SIZE
        self.drawers = [
            RectangleDrawer(self.position, self.size,
                            inside_color=ScanAnimation.BACKGROUND_COLOR),
        ]

    def set_canvas(self, canvas):
        Animation.set_canvas(self, canvas)
        assert(self.canvas)
        for drawer in self.drawers:
            drawer.set_canvas(canvas)

    def set_scan_workflow(self, page_scan, scan_workflow):
        GLib.idle_add(self.__set_scan_workflow, scan_workflow)

    def __set_scan_workflow(self, scan_workflow):
        scan_workflow.connect("scan-info", lambda _, x, y:
                              GLib.idle_add(self.__on_scan_info, (x, y)))
        scan_workflow.connect("scan-chunk", lambda _, line, chunk:
                              GLib.idle_add(self.__on_scan_chunk, line, chunk))
        scan_workflow.connect("scan-done", lambda _, img:
                              GLib.idle_add(self.__on_scan_done, img))
        scan_workflow.connect("process-done", lambda _, img, boxes:
                              GLib.idle_add(self.__on_process_done, img))

    def on_tick(self):
        for drawer in self.drawers:
            drawer.on_tick()

    def do_draw(self, cairo_ctx):
        for drawer in self.drawers:
            drawer.draw(cairo_ctx)

    def __on_scan_info(self, size):
        self.scan_animation = ScanAnimation(self.position, size, self.size)
        self.drawers = [
            RectangleDrawer(self.position, self.size,
                            inside_color=ScanAnimation.BACKGROUND_COLOR),
            self.scan_animation,
        ]
        assert(self.canvas)
        self.set_canvas(self.canvas)  # reset canvas on all new drawers
        for drawer in self.drawers:
            drawer.redraw()

    def __on_scan_chunk(self, line, img):
        assert(self.canvas)
        self.scan_animation.add_chunk(line, img)

    def __on_scan_done(self, img):
        size = fit(img.size, self.size)
        img = img.resize(size)
        self.scan_animation = None
        self.drawers = [
            RectangleDrawer(self.position, self.size,
                            inside_color=ScanAnimation.BACKGROUND_COLOR),
            PillowImageDrawer(self.position, img),
            SpinnerAnimation(((self.position[0] + (self.size[0] / 2) -
                               SpinnerAnimation.ICON_SIZE / 2),
                              (self.position[1] + (self.size[1] / 2) -
                               SpinnerAnimation.ICON_SIZE / 2))),
        ]
        self.set_canvas(self.canvas)  # reset canvas on all new drawers
        self.canvas.redraw()

    def __on_process_done(self, img):
        size = fit(img.size, self.size)
        img = img.resize(size)
        self.drawers = [
            RectangleDrawer(self.position, self.size,
                            inside_color=ScanAnimation.BACKGROUND_COLOR),
            PillowImageDrawer(self.position, img)
        ]
        self.set_canvas(self.canvas)  # reset canvas on all new drawers
        self.canvas.redraw()
