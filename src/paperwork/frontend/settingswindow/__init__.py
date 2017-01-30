#   Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
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
"""
Settings window.
"""

import platform
import os
import sys
import time

import gettext
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk
import logging
import pyinsane2
import pyocr

from paperwork_backend.util import find_language

from paperwork.frontend.util import load_uifile
from paperwork.frontend.util.actions import SimpleAction
from paperwork.frontend.util.canvas import Canvas
from paperwork.frontend.util.canvas.animations import ScanAnimation
from paperwork.frontend.util.canvas.drawers import PillowImageDrawer
from paperwork.frontend.util.config import DEFAULT_CALIBRATION_RESOLUTION
from paperwork.frontend.util.config import RECOMMENDED_SCAN_RESOLUTION
from paperwork.frontend.util.imgcutting import ImgGripHandler
from paperwork.frontend.util.jobs import Job, JobFactory, JobScheduler
from paperwork.frontend.util.jobs import JobFactoryProgressUpdater


_ = gettext.gettext
logger = logging.getLogger(__name__)


class JobDeviceFinder(Job):
    __gsignals__ = {
        'device-finding-start': (GObject.SignalFlags.RUN_LAST, None,
                                 ()),
        'device-found': (GObject.SignalFlags.RUN_LAST, None,
                         (GObject.TYPE_STRING,  # user name
                          GObject.TYPE_STRING,  # device id
                          GObject.TYPE_BOOLEAN)),  # is the active one
        'device-finding-end': (GObject.SignalFlags.RUN_LAST, None, ())
    }

    can_stop = False
    priority = 500

    def __init__(self, factory, id, selected_devid):
        Job.__init__(self, factory, id)
        self.__selected_devid = selected_devid

    @staticmethod
    def __get_dev_name(dev):
        """
        Return the human representation of a device

        Returns:
            A string
        """
        return ("%s %s" % (dev.vendor, dev.model))

    def do(self):
        self.emit("device-finding-start")
        self._wait(2.0)
        try:
            logger.info("Looking for scan devices ...")
            sys.stdout.flush()
            devices = pyinsane2.get_devices()
            for device in devices:
                selected = (self.__selected_devid == device.name)
                name = self.__get_dev_name(device)
                logger.info("Device found: [%s] -> [%s]" % (name, device.name))
                sys.stdout.flush()
                self.emit('device-found', name, device.name, selected)
            logger.info("End of scan for device")
        finally:
            self.emit("device-finding-end")


GObject.type_register(JobDeviceFinder)


class JobFactoryDeviceFinder(JobFactory):

    def __init__(self, settings_win, selected_devid):
        JobFactory.__init__(self, "DeviceFinder")
        self.__selected_devid = selected_devid
        self.__settings_win = settings_win

    def make(self):
        job = JobDeviceFinder(self, next(self.id_generator),
                              self.__selected_devid)
        job.connect('device-finding-start',
                    lambda job: GLib.idle_add(
                        self.__settings_win.on_device_finding_start_cb))
        job.connect('device-found',
                    lambda job, user_name, store_name, active:
                    GLib.idle_add(self.__settings_win.on_value_found_cb,
                                  self.__settings_win.device_settings['devid'],
                                  user_name, store_name, active))
        job.connect('device-finding-end',
                    lambda job: GLib.idle_add(
                        self.__settings_win.on_finding_end_cb,
                        self.__settings_win.device_settings['devid']))
        return job


class JobSourceFinder(Job):
    __gsignals__ = {
        'source-finding-start': (GObject.SignalFlags.RUN_LAST,
                                 None, ()),
        'source-found': (GObject.SignalFlags.RUN_LAST, None,
                         (GObject.TYPE_STRING,  # user name (translated)
                          GObject.TYPE_STRING,  # source name
                          GObject.TYPE_BOOLEAN, )),  # is the active one
        'source-finding-end': (GObject.SignalFlags.RUN_LAST,
                               None, ())
    }

    can_stop = False
    priority = 490

    def __init__(self, factory, id,
                 selected_source,
                 devid):
        Job.__init__(self, factory, id)
        self.__selected_source = selected_source
        self.__devid = devid

    def __get_source_name_translated(self, src_id):
        TRANSLATIONS = {
            'auto': _("Automatic"),
            'flatbed': _("Flatbed"),
            'adf': _("Automatic Feeder"),
        }
        if src_id.lower() in TRANSLATIONS:
            return TRANSLATIONS[src_id.lower()]
        logger.warning("No translation for source [%s]" % src_id)
        return src_id

    def do(self):
        self.emit("source-finding-start")
        try:
            logger.info("Looking for sources of device [%s]"
                        % (self.__devid))
            device = pyinsane2.Scanner(name=self.__devid)
            sys.stdout.flush()
            if 'source' in device.options:
                sources = device.options['source'].constraint
            else:
                sources = []
            logger.info("Sources found: %s" % str(sources))
            sys.stdout.flush()
            for source in sources:
                name = self.__get_source_name_translated(source)
                self.emit('source-found', name, source,
                          (source == self.__selected_source))
            logger.info("Got all the sources")
        finally:
            self.emit("source-finding-end")

GObject.type_register(JobSourceFinder)


class JobFactorySourceFinder(JobFactory):

    def __init__(self, settings_win, selected_source):
        JobFactory.__init__(self, "SourceFinder")
        self.__settings_win = settings_win
        self.__selected_source = selected_source

    def make(self, devid):
        job = JobSourceFinder(self, next(self.id_generator),
                              self.__selected_source, devid)
        job.connect('source-finding-start',
                    lambda job: GLib.idle_add(
                        self.__settings_win.on_finding_start_cb,
                        self.__settings_win.device_settings['source']))
        job.connect('source-found',
                    lambda job, user_name, store_name, active:
                    GLib.idle_add(
                        self.__settings_win.on_value_found_cb,
                        self.__settings_win.device_settings['source'],
                        user_name, store_name, active))
        job.connect('source-finding-end',
                    lambda job: GLib.idle_add(
                        self.__settings_win.on_finding_end_cb,
                        self.__settings_win.device_settings['source']))
        job.connect('source-finding-end',
                    lambda job: GLib.idle_add(
                        self.__settings_win.on_source_finding_end_cb))
        return job


class JobResolutionFinder(Job):
    __gsignals__ = {
        'resolution-finding-start': (GObject.SignalFlags.RUN_LAST,
                                     None, ()),
        'resolution-found': (GObject.SignalFlags.RUN_LAST, None,
                             (GObject.TYPE_STRING,  # user name
                              GObject.TYPE_INT,  # resolution value
                              GObject.TYPE_BOOLEAN)),  # is the active one
        'resolution-finding-end': (GObject.SignalFlags.RUN_LAST,
                                   None, ())
    }

    can_stop = False
    priority = 490

    def __init__(self, factory, id,
                 selected_resolution,
                 recommended_resolution,
                 devid):
        Job.__init__(self, factory, id)
        self.__selected_resolution = selected_resolution
        self.__recommended_resolution = recommended_resolution
        self.__devid = devid

    def __get_resolution_name(self, resolution):
        """
        Return the name corresponding to a resolution

        Arguments:
            resolution --- the resolution (integer)
        """
        txt = ("%d" % (resolution))
        if (resolution == self.__recommended_resolution):
            txt += _(' (recommended)')
        return txt

    def do(self):
        self.emit("resolution-finding-start")
        try:
            logger.info("Looking for resolution of device [%s]"
                        % (self.__devid))
            device = pyinsane2.Scanner(name=self.__devid)
            sys.stdout.flush()
            if 'resolution' in device.options:
                resolutions = device.options['resolution'].constraint
            else:
                resolutions = []
            if resolutions:
                logger.info("Resolutions found: %s" % str(resolutions))
            else:
                logger.warning(
                    "No possible resolutions specified. Assuming default"
                )
                resolutions = [75, 100, 150, 200, 300, 600, 1200]
            sys.stdout.flush()
            # Sometimes sane return the resolutions as a integer array,
            # sometimes as a range (-> tuple). So if it is a range, we turn
            # it into an array
            if isinstance(resolutions, tuple):
                interval = resolutions[2]
                if interval < 50:
                    interval = 50
                res_array = []
                for res in range(resolutions[0], resolutions[1] + 1,
                                 interval):
                    res_array.append(res)
                resolutions = res_array

            for resolution in resolutions:
                name = self.__get_resolution_name(resolution)
                self.emit('resolution-found', name, resolution,
                          (resolution == self.__selected_resolution))
            logger.info("Got all the resolutions")
        finally:
            self.emit("resolution-finding-end")


GObject.type_register(JobResolutionFinder)


class JobFactoryResolutionFinder(JobFactory):

    def __init__(self, settings_win, selected_resolution,
                 recommended_resolution):
        JobFactory.__init__(self, "ResolutionFinder")
        self.__settings_win = settings_win
        self.__selected_resolution = selected_resolution
        self.__recommended_resolution = recommended_resolution

    def make(self, devid):
        job = JobResolutionFinder(self, next(self.id_generator),
                                  self.__selected_resolution,
                                  self.__recommended_resolution, devid)
        job.connect('resolution-finding-start',
                    lambda job: GLib.idle_add(
                        self.__settings_win.on_finding_start_cb,
                        self.__settings_win.device_settings['resolution']))
        job.connect('resolution-found',
                    lambda job, store_name, user_name, active:
                    GLib.idle_add(
                        self.__settings_win.on_value_found_cb,
                        self.__settings_win.device_settings['resolution'],
                        store_name, user_name, active))
        job.connect('resolution-finding-end',
                    lambda job: GLib.idle_add(
                        self.__settings_win.on_finding_end_cb,
                        self.__settings_win.device_settings['resolution']))
        return job


class JobCalibrationScan(Job):
    __gsignals__ = {
        'calibration-scan-start': (GObject.SignalFlags.RUN_LAST, None,
                                   ()),
        'calibration-scan-info': (GObject.SignalFlags.RUN_LAST, None,
                                  (
                                      # expected size
                                      GObject.TYPE_INT,
                                      GObject.TYPE_INT,
                                  )),
        'calibration-scan-chunk': (GObject.SignalFlags.RUN_LAST, None,
                                   # line where to put the image
                                   (GObject.TYPE_INT,
                                    GObject.TYPE_PYOBJECT, )),  # PIL image
        'calibration-scan-done': (GObject.SignalFlags.RUN_LAST, None,
                                  (GObject.TYPE_PYOBJECT,  # Pillow image
                                   GObject.TYPE_INT, )),  # scan resolution
        'calibration-scan-error': (GObject.SignalFlags.RUN_LAST, None,
                                   (GObject.TYPE_STRING,)),  # error message
        'calibration-scan-canceled': (GObject.SignalFlags.RUN_LAST, None,
                                      ()),
    }

    can_stop = True
    priority = 495

    def __init__(self, factory, id, resolutions_store, devid, source=None):
        Job.__init__(self, factory, id)
        self.__resolutions_store = resolutions_store
        self.__devid = devid
        self.__source = source
        self.can_run = False

    def do(self):
        self.can_run = True
        self.emit('calibration-scan-start')

        try:
            (img, resolution) = self._do()
        except StopIteration as exc:
            logger.warning("Calibration scan failed: No paper to scan")
            self.emit('calibration-scan-error',
                      _("No paper to scan"))
            raise
        except Exception as exc:
            logger.warning("Calibration scan failed: {}".format(str(exc)))
            self.emit('calibration-scan-error',
                      _("Error while scanning: {}".format(str(exc))))
            raise

        self.emit('calibration-scan-done', img, resolution)

    def _do(self):
        # find the best resolution : the default calibration resolution
        # is not always available
        resolutions = [x[1] for x in self.__resolutions_store]
        resolutions.sort()

        resolution = DEFAULT_CALIBRATION_RESOLUTION
        for nresolution in resolutions:
            if nresolution > DEFAULT_CALIBRATION_RESOLUTION:
                break
            resolution = nresolution

        logger.info("Will do the calibration scan with a resolution of %d"
                    % resolution)

        # scan
        dev = pyinsane2.Scanner(name=self.__devid)

        if self.__source:
            if dev.options['source'].capabilities.is_active():
                dev.options['source'].value = self.__source
            logger.info("Scanner source set to '%s'" % self.__source)
        try:
            pyinsane2.set_scanner_opt(dev, 'resolution', [resolution])
        except pyinsane2.PyinsaneException as exc:
            logger.warning(
                "Unable to set scanner resolution to {}: {}".format(
                    resolution, exc
                )
            )
            logger.exception(exc)
            resolution = int(dev.options['resolution'].value)
            logger.warning("Falling back to current resolution: {}".format(
                resolution
            ))
        try:
            pyinsane2.set_scanner_opt(dev, 'mode', ["Color"])
        except pyinsane2.PyinsaneException as exc:
            logger.warning("Unable to set scanner mode !"
                           " May be 'Lineart': {}".format(exc))
            logger.exception(exc)

        try:
            pyinsane2.maximize_scan_area(dev)
        except pyinsane2.PyinsaneException as exc:
            logger.warning("Failed to maximize the scan area."
                           " May only scan part of the image: {}".format(exc))
            logger.exception(exc)

        scan_session = dev.scan(multiple=False)
        scan_size = scan_session.scan.expected_size
        self.emit('calibration-scan-info', scan_size[0], scan_size[1])

        last_line = 0
        try:
            while self.can_run:
                scan_session.scan.read()

                next_line = scan_session.scan.available_lines[1]
                if (next_line > last_line + 50):
                    chunk = scan_session.scan.get_image(last_line, next_line)
                    self.emit('calibration-scan-chunk', last_line, chunk)
                    last_line = next_line

                time.sleep(0)  # Give some CPU time to PyGtk
            if not self.can_run:
                self.emit('calibration-scan-canceled')
                scan_session.scan.cancel()
                return
        except EOFError:
            pass

        return (scan_session.images[-1], resolution)

    def stop(self, will_resume=False):
        assert(not will_resume)
        self.can_run = False
        self._stop_wait()

GObject.type_register(JobCalibrationScan)


class JobFactoryCalibrationScan(JobFactory):

    def __init__(self, settings_win, resolutions_store):
        JobFactory.__init__(self, "CalibrationScan")
        self.__settings_win = settings_win
        self.__resolutions_store = resolutions_store

    def make(self, devid, source):
        job = JobCalibrationScan(self, next(self.id_generator),
                                 self.__resolutions_store,
                                 devid, source)
        job.connect('calibration-scan-start',
                    lambda job:
                    GLib.idle_add(self.__settings_win.on_scan_start))
        job.connect('calibration-scan-info',
                    lambda job, size_x, size_y:
                    GLib.idle_add(self.__settings_win.on_scan_info,
                                  (size_x, size_y)))
        job.connect('calibration-scan-chunk',
                    lambda job, line, img:
                    GLib.idle_add(self.__settings_win.on_scan_chunk, line,
                                  img))
        job.connect('calibration-scan-error',
                    lambda job, error:
                    GLib.idle_add(self.__settings_win.on_scan_error, error))
        job.connect('calibration-scan-done',
                    lambda job, img, resolution:
                    GLib.idle_add(self.__settings_win.on_scan_done, img,
                                  resolution))
        job.connect('calibration-scan-canceled',
                    lambda job:
                    GLib.idle_add(self.__settings_win.on_scan_canceled))
        return job


class ActionSelectScanner(SimpleAction):
    enabled = True

    def __init__(self, settings_win):
        super(ActionSelectScanner, self).__init__("New scanner selected")
        self.__settings_win = settings_win

    def do(self):
        devid_settings = self.__settings_win.device_settings['devid']
        idx = devid_settings['gui'].get_active()
        if idx < 0:
            # happens when the scanner list has been updated
            # but no scanner has been found
            for setting in ['resolution', 'source']:
                settings = self.__settings_win.device_settings[setting]
                settings['stores']['loaded'].clear()
                settings['gui'].set_model(settings['stores']['loaded'])
                settings['gui'].set_sensitive(False)
            self.__settings_win.calibration["scan_button"].set_sensitive(False)
            return
        logger.info("Selected scanner: %d" % idx)

        devid = devid_settings['stores']['loaded'][idx][1]

        # no point in trying to stop the previous jobs, they are unstoppable
        job = self.__settings_win.job_factories['source_finder'].make(devid)
        self.__settings_win.schedulers['main'].schedule(job)
        job = self.__settings_win.job_factories['resolution_finder'].make(
            devid
        )
        self.__settings_win.schedulers['main'].schedule(job)


class ActionSelectSource(SimpleAction):
    enabled = True

    def __init__(self, settings_win):
        super(ActionSelectSource, self).__init__("New source selected")
        self.__settings_win = settings_win

    def do(self):
        source_settings = self.__settings_win.device_settings['source']
        idx = source_settings['gui'].get_active()
        self.__settings_win.calibration["scan_button"].set_sensitive(True)
        logger.info("Selected source: %d" % idx)
        if idx < 0:
            # happens when the scanner list has been updated
            # but no source has been found
            settings = self.__settings_win.device_settings['resolution']
            settings['stores']['loaded'].clear()
            settings['gui'].set_model(settings['stores']['loaded'])
            settings['gui'].set_sensitive(False)
            return


class ActionToggleOCRState(SimpleAction):
    enabled = True

    def __init__(self, settings_win):
        super(ActionToggleOCRState, self).__init__("Toggle OCR state")
        self.__settings_win = settings_win

    def do(self):
        SimpleAction.do(self)
        self.__settings_win.set_ocr_opts_state()


class ActionApplySettings(SimpleAction):
    enabled = True

    def __init__(self, settings_win, config):
        super(ActionApplySettings, self).__init__("Apply settings")
        self.__settings_win = settings_win
        self.__config = config

    def do(self):
        need_reindex = False
        workdir = self.__settings_win.workdir_chooser.get_filename()
        if workdir != self.__config['workdir'].value:
            self.__config['workdir'].value = workdir
            need_reindex = True

        try:
            setting = self.__settings_win.device_settings['devid']
            idx = setting['gui'].get_active()
            if idx >= 0:
                devid = setting['stores']['loaded'][idx][1]
                self.__config['scanner_devid'].value = devid

            setting = self.__settings_win.device_settings['source']
            idx = setting['gui'].get_active()
            if idx >= 0:
                source = setting['stores']['loaded'][idx][1]
                self.__config['scanner_source'].value = source

            has_feeder = self.__settings_win.device_settings['has_feeder']
            self.__config['scanner_has_feeder'].value = has_feeder

            setting = self.__settings_win.device_settings['resolution']
            idx = setting['gui'].get_active()
            if idx >= 0:
                resolution = setting['stores']['loaded'][idx][1]
                self.__config['scanner_resolution'].value = resolution
        except Exception as exc:
            logger.warning("Failed to update scanner settings: %s" % str(exc))

        setting = self.__settings_win.ocr_settings['enabled']
        enabled = setting['gui'].get_active()
        self.__config['ocr_enabled'].value = enabled

        setting = self.__settings_win.ocr_settings['lang']
        idx = setting['gui'].get_active()
        if idx >= 0:
            lang = setting['store'][idx][1]
            self.__config['ocr_lang'].value = lang

        if self.__settings_win.grips is not None:
            coords = self.__settings_win.grips.get_coords()
            self.__config['scanner_calibration'].value = (
                self.__settings_win.calibration['resolution'], coords)

        self.__config.write()

        self.__settings_win.hide()

        if need_reindex:
            self.__settings_win.emit("need-reindex")
        self.__settings_win.emit("config-changed")


class ActionScanCalibration(SimpleAction):
    enabled = True

    def __init__(self, settings_win):
        self.settings_win = settings_win
        super(ActionScanCalibration, self).__init__("Scan calibration sheet")

    def do(self):
        win = self.settings_win
        setting = win.device_settings['devid']
        idx = setting['gui'].get_active()
        assert(idx >= 0)
        devid = setting['stores']['loaded'][idx][1]

        setting = win.device_settings['source']
        idx = setting['gui'].get_active()
        if idx >= 0:
            source = setting['stores']['loaded'][idx][1]
        else:
            source = None

        job = win.job_factories['scan'].make(devid, source)
        win.schedulers['main'].schedule(job)


class SettingsWindow(GObject.GObject):
    """
    Settings window.
    """

    __gsignals__ = {
        'need-reindex': (GObject.SignalFlags.RUN_LAST, None, ()),
        'config-changed': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, main_scheduler, mainwindow_gui, config):
        super(SettingsWindow, self).__init__()

        self.schedulers = {
            'main': main_scheduler,
            'progress': JobScheduler('progress'),
        }
        self.local_schedulers = [
            self.schedulers['progress'],
        ]

        widget_tree = load_uifile(
            os.path.join("settingswindow", "settingswindow.glade"))

        distrib = platform.dist()
        if distrib:
            distrib = distrib[0].lower()
            logger.info("Distribution: [%s]" % distrib)
            for widget in widget_tree.get_objects():
                if type(widget) == Gtk.LinkButton:
                    uri = widget.get_uri()
                    uri += "#" + distrib
                    widget.set_uri(uri)

        self.window = widget_tree.get_object("windowSettings")
        self.window.set_transient_for(mainwindow_gui)

        self.__config = config

        self.workdir_chooser = widget_tree.get_object("filechooserbutton")

        self.ocr_settings = {
            "enabled": {
                'gui': widget_tree.get_object("checkbuttonOcrEnabled")
            },
            "lang": {
                'gui': widget_tree.get_object("comboboxLang"),
                'store': widget_tree.get_object("liststoreOcrLang"),
            },
        }

        actions = {
            "delete-event": (
                [self.window],
                ActionApplySettings(self, config),
            ),
            "toggle_ocr": (
                [self.ocr_settings['enabled']['gui']],
                ActionToggleOCRState(self),
            ),
            "select_scanner": (
                [widget_tree.get_object("comboboxDevices")],
                ActionSelectScanner(self)
            ),
            "select_source": (
                [widget_tree.get_object("comboboxScanSources")],
                ActionSelectSource(self)
            ),
            "scan_calibration": (
                [widget_tree.get_object("buttonScanCalibration")],
                ActionScanCalibration(self)
            )
        }

        self.device_settings = {
            "devid": {
                'gui': widget_tree.get_object("comboboxDevices"),
                'stores': {
                    'loaded': widget_tree.get_object("liststoreDevice"),
                },
                'nb_elements': 0,
                'active_idx': -1,
            },
            "has_feeder": False,
            "source": {
                'gui': widget_tree.get_object("comboboxScanSources"),
                'stores': {
                    'loaded': widget_tree.get_object("liststoreScanSources"),
                },
                'nb_elements': 0,
                'active_idx': -1,
            },
            "resolution": {
                'gui': widget_tree.get_object("comboboxResolution"),
                'stores': {
                    'loaded': widget_tree.get_object("liststoreResolution"),
                },
                'nb_elements': 0,
                'active_idx': -1,
            },
        }

        img_scrollbars = widget_tree.get_object("scrolledwindowCalibration")
        img_canvas = Canvas(img_scrollbars)
        img_canvas.set_visible(True)
        img_scrollbars.add(img_canvas)

        self.calibration = {
            "scan_button": widget_tree.get_object("buttonScanCalibration"),
            "image_gui": img_canvas,
            "image": None,
            "image_eventbox": widget_tree.get_object("eventboxCalibration"),
            "image_scrollbars": img_scrollbars,
            "resolution": DEFAULT_CALIBRATION_RESOLUTION,
            "zoom": widget_tree.get_object("adjustmentZoom"),
        }

        self.grips = None

        self.progressbar = widget_tree.get_object("progressbarScan")
        self.__scan_start = 0.0

        self.job_factories = {
            "device_finder": JobFactoryDeviceFinder(
                self, config['scanner_devid'].value
            ),
            "source_finder": JobFactorySourceFinder(
                self, config['scanner_source'].value
            ),
            "resolution_finder": JobFactoryResolutionFinder(
                self,
                config['scanner_resolution'].value,
                RECOMMENDED_SCAN_RESOLUTION
            ),
            "scan": JobFactoryCalibrationScan(
                self,
                self.device_settings['resolution']['stores']['loaded']
            ),
            "progress_updater": JobFactoryProgressUpdater(self.progressbar),
        }

        ocr_tools = pyocr.get_available_tools()
        if len(ocr_tools) == 0:
            ocr_langs = []
        else:
            ocr_langs = ocr_tools[0].get_available_languages()
        ocr_langs = self.__get_short_to_long_langs(ocr_langs)
        ocr_langs.sort(key=lambda lang: lang[1])
        ocr_langs.insert(0, (None, _("Disable OCR")))

        self.ocr_settings['lang']['store'].clear()
        for (short_lang, long_lang) in ocr_langs:
            self.ocr_settings['lang']['store'].append([long_lang, short_lang])

        for (k, v) in actions.items():
            v[1].connect(v[0])

        self.window.connect("destroy", self.__on_destroy)

        self.display_config(config)

        self.window.set_visible(True)

        for scheduler in self.local_schedulers:
            scheduler.start()

        job = self.job_factories['device_finder'].make()
        self.schedulers['main'].schedule(job)

    @staticmethod
    def __get_short_to_long_langs(short_langs):
        """
        For each short language name, figures out its long name.

        Arguments:
            short_langs --- Array of strings. Each string is the short name of
            a language. Should be 3 characters long (more should be fine as
            well)

        Returns:
            Tuples: (short name, long name)
        """
        langs = []
        for short_lang in short_langs:
            try:
                extra = short_lang[3:]
                short_lang = short_lang[:3]
                long_lang = short_lang
                if extra != "" and (extra[0] == "-" or extra[0] == "_"):
                    extra = extra[1:]
                lang = find_language(short_lang, allow_none=True)
                if lang:
                    long_lang = lang.name
                if extra != "":
                    long_lang += " (%s)" % (extra)
                langs.append((short_lang, long_lang))
            except KeyError:
                logger.error("Warning: Long name not found for language "
                             "'%s'." % short_lang)
                logger.warning("  Will use short name as long name.")
                langs.append((short_lang, short_lang))
        return langs

    def on_finding_start_cb(self, settings):
        settings['gui'].set_sensitive(False)
        settings['stores']['loaded'].clear()
        settings['nb_elements'] = 0
        settings['active_idx'] = -1

    def on_device_finding_start_cb(self):
        self.calibration["scan_button"].set_sensitive(False)
        self.on_finding_start_cb(self.device_settings['devid'])
        for element in self.device_settings.values():
            if isinstance(element, dict) and 'gui' in element:
                element['gui'].set_sensitive(False)

    def on_value_found_cb(self, settings,
                          user_name, store_name, active):
        store_line = [user_name, store_name]
        logger.info("Got value [%s]" % store_line)
        settings['stores']['loaded'].append(store_line)
        if active:
            settings['active_idx'] = settings['nb_elements']
        settings['nb_elements'] += 1

    def on_finding_end_cb(self, settings):
        settings['gui'].set_sensitive(len(settings['stores']['loaded']) > 0)
        settings['gui'].set_model(settings['stores']['loaded'])
        if settings['active_idx'] >= 0:
            settings['gui'].set_active(settings['active_idx'])
        else:
            settings['gui'].set_active(0)

    def on_source_finding_end_cb(self):
        settings = self.device_settings['source']
        sources = [x[1].lower() for x in settings['stores']['loaded']]
        has_feeder = False
        logger.info("Scanner sources: %s" % str(sources))
        for src in sources:
            if "feeder" in src:
                has_feeder = True
            if "adf" in src:
                has_feeder = True
            if has_feeder:
                break
        self.device_settings['has_feeder'] = has_feeder

    def set_mouse_cursor(self, cursor):
        self.window.get_window().set_cursor({
            "Normal": None,
            "Busy": Gdk.Cursor.new(Gdk.CursorType.WATCH),
        }[cursor])

    def on_scan_start(self):
        self.calibration["scan_button"].set_sensitive(False)
        self.set_mouse_cursor("Busy")

        self.calibration['image_gui'].remove_all_drawers()

        self.__scan_start = time.time()

        self.__scan_progress_job = self.job_factories['progress_updater'].make(
            value_min=0.0, value_max=1.0,
            total_time=self.__config['scan_time'].value['calibration'])
        self.schedulers['progress'].schedule(self.__scan_progress_job)

    def on_scan_info(self, size):
        self.calibration['scan_drawer'] = ScanAnimation(
            (0, 0),
            size, self.calibration['image_gui'].visible_size)
        self.calibration['image_gui'].add_drawer(
            self.calibration['scan_drawer'])

    def on_scan_chunk(self, line, img):
        self.calibration['scan_drawer'].add_chunk(line, img)

    def _on_scan_end(self):
        self.progressbar.set_fraction(0.0)
        self.schedulers['progress'].cancel(self.__scan_progress_job)
        self.calibration['image_gui'].remove_all_drawers()
        self.set_mouse_cursor("Normal")

    def on_scan_error(self, error):
        self._on_scan_end()
        self.calibration["scan_button"].set_sensitive(False)
        msg = (_("Error while scanning: {}").format(error))
        flags = (Gtk.DialogFlags.MODAL |
                 Gtk.DialogFlags.DESTROY_WITH_PARENT)
        dialog = Gtk.MessageDialog(transient_for=self.window,
                                   flags=flags,
                                   message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.OK,
                                   text=msg)
        dialog.connect("response", lambda dialog, response:
                       GLib.idle_add(dialog.destroy))
        dialog.show_all()

    def on_scan_done(self, img, scan_resolution):
        scan_stop = time.time()
        self.__config['scan_time'].value['calibration'] = (
            scan_stop - self.__scan_start
        )

        self._on_scan_end()

        self.calibration['image'] = img
        self.calibration['resolution'] = scan_resolution
        calibration = self.__config['scanner_calibration'].value
        if calibration:
            calibration = calibration[1]
        img_drawer = PillowImageDrawer((0, 0), self.calibration['image'])
        self.calibration['image_gui'].add_drawer(img_drawer)
        self.grips = ImgGripHandler(
            img_drawer, img_drawer.size,
            self.calibration['zoom'],
            default_grips_positions=calibration,
            canvas=self.calibration['image_gui']
        )
        self.calibration['image_gui'].add_drawer(self.grips)
        self.grips.visible = True
        self.calibration["scan_button"].set_sensitive(True)

    def on_scan_canceled(self):
        self.schedulers['progress'].cancel(self.__scan_progress_job)

        self.calibration['image_gui'].unforce_size()
        self.calibration['image_gui'].remove_all_drawers()
        self.calibration['scan_drawer'] = None
        self.set_mouse_cursor("Normal")
        self.calibration["scan_button"].set_sensitive(True)

    def display_config(self, config):
        self.workdir_chooser.set_current_folder(config['workdir'].value)

        ocr_enabled = config['ocr_enabled'].value
        if config['ocr_lang'].value is None:
            ocr_enabled = False
        self.ocr_settings['enabled']['gui'].set_active(ocr_enabled)

        idx = 0
        current_ocr_lang = config['ocr_lang'].value
        for (long_lang, short_lang) in self.ocr_settings['lang']['store']:
            if short_lang == current_ocr_lang:
                self.ocr_settings['lang']['gui'].set_active(idx)
            idx += 1
        self.set_ocr_opts_state()

    def set_ocr_opts_state(self):
        ocr_enabled = self.ocr_settings['enabled']['gui'].get_active()
        for (k, v) in self.ocr_settings.items():
            if k == "enabled":
                continue
            v['gui'].set_sensitive(ocr_enabled)

    def __on_destroy(self, window=None):
        logger.info("Settings window destroyed")
        for scheduler in self.local_schedulers:
            scheduler.stop()

    def hide(self):
        """
        Hide and destroy the settings window.
        """
        self.window.destroy()

GObject.type_register(SettingsWindow)
