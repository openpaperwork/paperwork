import logging

import pillowfight

from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.fs import Fs
import openpaperwork_core
import openpaperwork_core.promise

from openpaperwork_gtk.interfaces.activity import ActivityListener
from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.pillow import PillowDrawer
from openpaperwork_gtk.interfaces.screenshot import Screenshot
from openpaperwork_gtk.interfaces.screenshot import ScreenshotProvider

from paperwork_backend.interfaces.i18n_scanner import I18nScanner
from paperwork_backend.interfaces.scan import (
    Scan,
    ScanListener
)
import paperwork_backend.cairo.pillow

from paperwork_gtk import _
from paperwork_gtk.interfaces.drawers import CalibrationDrawerFactory
from paperwork_gtk.interfaces.drawers import ScanDrawerFactory
from paperwork_gtk.interfaces.settings import (
    GtkSettingsScanCalibration,
    GtkSettingsScannerSetting
)
from paperwork_gtk.interfaces.settings_dialog import (
    SettingsDialog,
    SettingsDialogComponent
)
from paperwork_gtk.interfaces.zoom import Zoom


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    ScanListener,
    ScreenshotProvider,
    SettingsDialogComponent,
    GtkSettingsScanCalibration,
    GtkSettingsScannerSetting,
):
    PRIORITY = 10000

    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            {
                "interface": ActivityListener,
                "defaults": [],
            },
            {
                'interface': Config,
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': CalibrationDrawerFactory,
                'defaults': ['paperwork_gtk.drawer.calibration'],
            },
            {
                "interface": Fs,
                "defaults": ["openpaperwork_gtk.fs.gio"],
            },
            {
                "interface": I18nScanner,
                "defaults": ["paperwork_backend.i18n.scanner"],
            },
            {
                'interface': PillowDrawer,
                'defaults': ['openpaperwork_gtk.drawer.pillow'],
            },
            {
                'interface': ScanDrawerFactory,
                'defaults': ['paperwork_gtk.drawer.calibration'],
            },
            # Optional:
            # {
            #     'interface': 'gtk_zoomable',
            #     'defaults': [
            #         'paperwork_gtk.gesture.zoom',
            #         'paperwork_gtk.keyboard_shortcut.zoom',
            #     ],
            # },
            {
                'interface': GtkResources,
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': SettingsDialog,
                'defaults': ['paperwork_gtk.settings'],
            },
            {
                'interface': Scan,
                'defaults': ['paperwork_backend.docscan.libinsane'],
            },
            {
                'interface': Screenshot,
                'defaults': ['openpaperwork_gtk.screenshots'],
            },
            {
                "interface": Zoom,
                "defaults": [],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.widget_tree = None
        self.settings_widget_tree = None
        self.size_allocate_connect_id = None
        self.scan_height = 0
        self.scan_width = 0
        self.scan_img = None

    def complete_settings(self, settings_widget_tree):
        self.settings_widget_tree = settings_widget_tree
        self.widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.settings.scanner", "calibration.glade"
        )

        self.size_allocate_connect_id = self.widget_tree.get_object(
            "calibration_scroll"
        ).connect(
            "size-allocate", self._update_calibration_scroll_area_size
        )
        self.value_changed_connect_id = self.widget_tree.get_object(
            "calibration_scale_adjustment"
        ).connect(
            "value-changed", self._update_calibration_area_size_based_on_scale
        )

        self.widget_tree.get_object("calibration_back").connect(
            "clicked", self.hide_calibration_screen
        )
        self.widget_tree.get_object("calibration_scan").connect(
            "clicked", self._start_scan
        )
        self.widget_tree.get_object("calibration_maximize").connect(
            "clicked", self._on_maximize
        )
        self.widget_tree.get_object("calibration_automatic").connect(
            "clicked", self._guess_scan_borders
        )

        drawing_area = self.widget_tree.get_object("calibration_area")
        self.core.call_all(ScanDrawerFactory.draw_scan_start, drawing_area)

        self.core.call_all(
            SettingsDialog.add_setting_screen,
            settings_widget_tree,
            "calibration",
            self.widget_tree.get_object("calibration_header"),
            self.widget_tree.get_object("calibration_body"),
        )

    def complete_scanner_settings(
            self, settings_widget_tree, parent_widget_tree,
            list_scanner_promise):
        assert self.widget_tree is not None

        def set_sensitive():
            dev_id = self.core.call_success(Config.config_get, "scanner_dev_id")
            parent_widget_tree.get_object("scanner_calibration").set_sensitive(
                True if dev_id is not None and dev_id != "" else False
            )

        set_sensitive()
        self.core.call_all(
            Config.config_add_observer, "scanner_dev_id", set_sensitive
        )

        parent_widget_tree.get_object("scanner_calibration").connect(
            "clicked", self.display_calibration_screen, settings_widget_tree
        )

    def on_settings_closed(self, settings_widget_tree):
        drawing_area = self.widget_tree.get_object("calibration_area")
        self.core.call_all(ScanDrawerFactory.draw_scan_stop, drawing_area)
        if self.value_changed_connect_id is not None:
            drawing_area.disconnect(self.value_changed_connect_id)
            self.value_changed_connect_id = None
        if self.size_allocate_connect_id is not None:
            self.widget_tree.get_object("calibration_scroll").disconnect(
                self.size_allocate_connect_id
            )
            self.size_allocate_connect_id = None

    def display_calibration_screen(self, *args, **kwargs):
        LOGGER.info("Switching to calibration screen")
        self.core.call_all(
            SettingsDialog.show_setting_screen, self.settings_widget_tree, "calibration"
        )

        sources = self.widget_tree.get_object("calibration_sources")
        sources.clear()
        sources.append(("", _("Loading ...")))

        combobox = self.widget_tree.get_object("calibration_source")
        combobox.set_active(0)
        combobox.set_sensitive(False)

        buttons = [
            'calibration_automatic',
            'calibration_maximize',
            'calibration_scan',
        ]
        for button in buttons:
            self.widget_tree.get_object(button).set_sensitive(False)

        self.core.call_all(
            Zoom.on_zoomable_widget_new,
            self.widget_tree.get_object("calibration_scroll"),
            self.widget_tree.get_object("calibration_scale_adjustment")
        )

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=(ActivityListener.on_busy,)
        )
        promise = promise.then(
            # drop the return value of call_all()
            lambda *args, **kwargs: None
        )
        promise = promise.then(self.core.call_success(
            Scan.scan_get_scanner_promise
        ))
        promise = promise.then(self._show_sources)
        promise = promise.then(openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=(ActivityListener.on_idle,)
        ))
        self.core.call_success(Scan.scan_schedule, promise)

    def _show_sources(self, dev=None):
        sources = []
        if dev is not None:
            sources = [
                (
                    source.get_name(),
                    self.core.call_success(
                        I18nScanner.i18n_scanner_source, source.get_name()
                    ),
                )
                for source in dev.dev.get_children()
            ]
        LOGGER.info("Found %d sources", len(sources))

        sources_widget = self.widget_tree.get_object("calibration_sources")
        sources_widget.clear()
        for src in sources:
            LOGGER.info("Source: %s ; %s", src[0], src[1])
            sources_widget.append(src)

        combobox = self.widget_tree.get_object("calibration_source")
        combobox.set_active(0)
        combobox.set_sensitive(True)

        self.widget_tree.get_object("calibration_scan").set_sensitive(True)

    def hide_calibration_screen(self, *args, **kwargs):
        LOGGER.info("Switching back to settings")
        self.core.call_all(
            SettingsDialog.show_setting_screen, self.settings_widget_tree, "main"
        )
        self.core.call_all(
            Zoom.on_zoomable_widget_destroy,
            self.widget_tree.get_object("calibration_area"),
            self.widget_tree.get_object("calibration_scale_adjustment")
        )

    def _start_scan(self, button):
        combobox = self.widget_tree.get_object("calibration_source")
        source_idx = combobox.get_active()
        sources = self.widget_tree.get_object("calibration_sources")
        source = sources[source_idx][0]

        LOGGER.info("Starting calibration scan on %s ...", source)

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=(ActivityListener.on_busy,)
        )
        promise = promise.then(
            # drop the return value of call_all()
            lambda *args, **kwargs: None
        )
        # calibration is always done at 75 DPI
        promise = promise.then(
            self.core.call_success(
                Scan.scan_promise, source_id=source, resolution=75
            )[1]
        )
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, self._scan
        ))
        promise = promise.then(self._on_scan_end)
        promise = promise.then(openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=(ActivityListener.on_idle,)
        ))
        self.core.call_success(Scan.scan_schedule, promise)
        self.widget_tree.get_object("calibration_scan").set_sensitive(False)

    def _scan(self, args):
        (source, scan_id, img_generator) = args
        # just unroll the image generator.
        # --> we catch the content using the the on_scan_XXXX callbacks.
        img = None
        for (idx, img) in enumerate(img_generator):
            LOGGER.info("Page %d scanned: %s", idx, img.size)
        return img

    def on_scan_page_start(self, scan_id, page_nb, scan_params):
        (self.scan_width, self.scan_height) = (
            paperwork_backend.cairo.pillow.limit_img_size((
                scan_params.get_width(),
                scan_params.get_height(),
            ))
        )
        if self.widget_tree is None:
            return
        self._update_calibration_area_size_based_on_scroll()
        self._update_calibration_scroll_area_size()

    def _update_calibration_area_size_based_on_scroll(self, *args, **kwargs):
        scroll = self.widget_tree.get_object("calibration_scroll")
        widget_height = scroll.get_allocated_height()
        factor = widget_height / self.scan_height
        self.widget_tree.get_object("calibration_scale_adjustment").set_value(
            factor
        )
        # signal 'value-changed' will trigger the update and redraw
        self.widget_tree.get_object("calibration_scale_adjustment").set_lower(
            factor
        )

    def _update_calibration_area_size_based_on_scale(self, *args, **kwargs):
        adj = self.widget_tree.get_object(
            "calibration_scale_adjustment"
        )
        factor = adj.get_value()
        LOGGER.debug(
            "Scale: %f < %f < %f", adj.get_lower(), factor, adj.get_upper()
        )

        widget_width = int(self.scan_width * factor)
        widget_height = int(self.scan_width * factor)

        LOGGER.debug(
            "Calibratrion widget size: (%d, %d)", widget_width, widget_height
        )
        self.widget_tree.get_object("calibration_area").set_size_request(
            widget_width, widget_height
        )
        self.widget_width = widget_width

    def _update_calibration_scroll_area_size(self, *args, **kwargs):
        # scroll area must have the same proportion than the scanned image
        scroll = self.widget_tree.get_object("calibration_scroll")
        widget_height = scroll.get_allocated_height()
        if self.scan_height <= 0:
            ratio = 1.0 / 1.414
        else:
            ratio = self.scan_width / self.scan_height
        widget_width = max(widget_height * ratio, 300)
        LOGGER.debug(
            "Calibration scroll window size: (%d, %d)",
            widget_width, widget_height
        )
        scroll.set_size_request(widget_width, -1)

        if self.scan_height > 0:
            factor = widget_height / self.scan_height
            adj = self.widget_tree.get_object("calibration_scale_adjustment")
            if adj.get_value() < factor:
                adj.set_value(factor)
            adj.set_lower(factor)

    def _on_scan_end(self, scan_img=None):
        if self.widget_tree is not None:
            buttons = [
                'calibration_automatic',
                'calibration_maximize',
                'calibration_scan'
            ]
            for button in buttons:
                self.widget_tree.get_object(button).set_sensitive(True)

            drawing_area = self.widget_tree.get_object("calibration_area")
            self.core.call_all(ScanDrawerFactory.draw_scan_stop, drawing_area)

        if scan_img is None:
            LOGGER.info("No page scanned. Can't do calibration")
            return

        (self.scan_width, self.scan_height) = (
            paperwork_backend.cairo.pillow.limit_img_size(scan_img.size)
        )
        self.scan_img = scan_img

        LOGGER.info("Calibration scan ready")

        if self.core.call_success(Config.config_get, "scanner_calibration") is None:
            # Put the frame a little bit inside the image to make the
            # corner handles more visible
            calibration = [
                min(50, self.scan_width),
                min(50, self.scan_height),
                max(self.scan_width - 50, 0),
                max(self.scan_height - 50, 0),
            ]
            LOGGER.info("Setting default calibration area: %s", calibration)
            self.core.call_all(
                Config.config_put, "scanner_calibration", calibration
            )

        self.core.call_all(PillowDrawer.draw_pillow_start, drawing_area, scan_img)
        self.core.call_all(
            CalibrationDrawerFactory.draw_calibration_start, drawing_area,
            (self.scan_width, self.scan_height)
        )

    def _on_maximize(self, button):
        if self.scan_height <= 0 or self.scan_width <= 0:
            return
        self.core.call_all(
            Config.config_put, "scanner_calibration",
            [0, 0, self.scan_width, self.scan_height]
        )

    def _guess_scan_borders(self, button=None):
        if self.scan_img is None:
            return

        LOGGER.info("Guessing scan borders")

        def find_scan_borders(scan_img):
            frame = pillowfight.find_scan_borders(scan_img)
            return frame

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=(ActivityListener.on_busy,)
        )
        promise = promise.then(lambda *args, **kwargs: self.scan_img)
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, find_scan_borders
        ))
        promise = promise.then(
            lambda frame: self.core.call_all(
                Config.config_put, "scanner_calibration", list(frame)
            )
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self.core.call_all, ActivityListener.on_idle)
        promise.schedule()

    def screenshot_snap_all_doc_widgets(self, out_dir):
        if self.widget_tree is None:
            return
        if self.settings_widget_tree is None:
            return

        body = self.widget_tree.get_object("calibration_body")
        if body is None:
            return
        self.core.call_success(
            Screenshot.screenshot_snap_widget, body,
            self.core.call_success(
                Fs.fs_join, out_dir, "settings_calibration_dialog.png"
            ),
            margins=(100, 100, 100, 100)
        )

    @openpaperwork_core.noop
    def on_scan_feed_start(self, scan_id):
        pass

    @openpaperwork_core.noop
    def on_scan_started(self, scan_id):
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
