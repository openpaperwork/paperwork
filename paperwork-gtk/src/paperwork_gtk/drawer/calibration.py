"""
Ensure calibration is displayed when a scan is running.
"""

import logging

import openpaperwork_core

from openpaperwork_core.interfaces.config import Config

from paperwork_backend.interfaces.cropping import PredefinedCropping
from paperwork_backend.interfaces.scan import Scan
from paperwork_backend.interfaces.scan import ScanListener

from paperwork_gtk.interfaces.drawers import CalibrationDrawerFactory
from paperwork_gtk.interfaces.drawers import FrameDrawerFactory
from paperwork_gtk.interfaces.drawers import ScanDrawerFactory


LOGGER = logging.getLogger(__name__)


class Drawer:
    def __init__(self, core, drawing_area, read_only=False):
        self.core = core
        self.drawing_area = drawing_area
        self.content_full_size = None
        self.scan_id = None
        self.active = False
        self.drawer = None
        self.read_only = read_only

    def _get_frame(self):
        return self.core.call_success(Config.config_get, "scanner_calibration")

    def _set_frame(self, frame):
        self.core.call_all(Config.config_put, "scanner_calibration", frame)

    def set_content_full_size(self, size):
        self.content_full_size = size

    def start(self):
        if self.active:
            self.stop()

        self.core.call_all(
            Config.config_add_observer, "scanner_calibration",
            self.request_redraw
        )
        self.drawer = self.core.call_success(
            FrameDrawerFactory.draw_frame_start, self.drawing_area, self.content_full_size,
            self._get_frame,
            self._set_frame if not self.read_only else None
        )
        self.active = True

    def request_redraw(self, *args, **kwargs):
        if self.drawer is None:
            return
        self.drawer.request_redraw()

    def stop(self):
        if not self.active:
            return
        self.core.call_all(FrameDrawerFactory.draw_frame_stop, self.drawing_area)
        self.core.call_all(
            Config.config_remove_observer, "scanner_calibration",
            self.request_redraw
        )
        self.active = False


class Plugin(
    openpaperwork_core.PluginBase,
    CalibrationDrawerFactory,
    ScanDrawerFactory,
    ScanListener,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Config,
                defaults=['openpaperwork_core.config'],
            ),
            openpaperwork_core.Dependency(
                interface=FrameDrawerFactory,
                defaults=['paperwork_gtk.drawer.frame'],
            ),
            openpaperwork_core.Dependency(
                interface=Scan,
                defaults=['paperwork_backend.docscan.libinsane'],
            ),
            openpaperwork_core.Dependency(
                interface=PredefinedCropping,
                defaults=[
                    'paperwork_backend.guesswork.cropping.calibration'
                ]
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.drawers = {}  # drawing_area --> drawer
        self.scan_id_to_drawers = {}  # int --> drawer

    def draw_calibration_start(self, drawing_area, content_full_size, read_only=False):
        drawer = Drawer(self.core, drawing_area, read_only)
        drawer.set_content_full_size(content_full_size)
        drawer.start()
        self.drawers[drawing_area] = drawer

    def draw_calibration_stop(self, drawing_area):
        if drawing_area not in self.drawers:
            return
        self.drawers.pop(drawing_area).stop()

    def draw_scan_start(self, drawing_area, scan_id=None):
        if drawing_area in self.drawers:
            drawer = self.drawers[drawing_area]
        elif scan_id is not None and scan_id in self.scan_id_to_drawers:
            drawer = self.scan_id_to_drawers[scan_id]
            self.drawers.pop(drawer.drawing_area, None)
            drawer.stop()
            drawer.drawing_area = drawing_area
            drawer.start()
        else:
            drawer = Drawer(self.core, drawing_area, read_only=True)

        drawer.scan_id = scan_id
        self.scan_id_to_drawers[scan_id] = drawer
        self.drawers[drawing_area] = drawer

    @openpaperwork_core.noop
    def draw_scan_get_scan_size(self, scan_id):
        pass

    def draw_scan_stop(self, drawing_area):
        if drawing_area in self.drawers:
            self.drawers.pop(drawing_area).stop()

    def on_scan_page_start(self, scan_id, page_nb, scan_params):
        for drawer in self.drawers.values():
            if drawer.scan_id is None or scan_id == drawer.scan_id:
                drawer.set_content_full_size(
                    (scan_params.get_width(), scan_params.get_height())
                )
                drawer.start()

    @openpaperwork_core.noop
    def on_scan_started(self, scan_id):
        pass

    @openpaperwork_core.noop
    def on_scan_feed_start(self, scan_id):
        pass

    @openpaperwork_core.noop
    def on_scan_chunk(self, scan_id, scan_params, img_chunk):
        pass

    @openpaperwork_core.noop
    def on_scan_page_end(self, scan_id, page_nb, img):
        pass

    @openpaperwork_core.noop
    def on_scan_feed_end(self, scan_id):
        pass
