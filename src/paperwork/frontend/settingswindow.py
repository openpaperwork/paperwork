#   Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012  Jerome Flesch
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

import PIL.Image
import os
import sys
import time

import gettext
import logging
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk
import pycountry
import pyocr.pyocr as pyocr

import pyinsane.abstract_th as pyinsane

from paperwork.backend.config import PaperworkConfig
from paperwork.frontend.actions import SimpleAction
from paperwork.frontend.img_cutting import ImgGripHandler
from paperwork.frontend.jobs import Job, JobFactory, JobScheduler, JobFactoryProgressUpdater
from paperwork.util import image2pixbuf
from paperwork.util import load_uifile
from paperwork.util import set_scanner_opt
from paperwork.util import maximize_scan_area


_ = gettext.gettext
logger = logging.getLogger(__name__)

RECOMMENDED_RESOLUTION = 300


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
        try:
            logger.info("Looking for scan devices ...")
            sys.stdout.flush()
            devices = pyinsane.get_devices()
            for device in devices:
                selected = (self.__selected_devid == device.name)
                name = self.__get_dev_name(device)
                logger.info("Device found: [%s] -> [%s]" % (name, device.name))
                sys.stdout.flush()
                self.emit('device-found', name, device.name, selected)
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
                    lambda job: GObject.idle_add(
                        self.__settings_win.on_device_finding_start_cb))
        job.connect('device-found',
                    lambda job, user_name, store_name, active:
                    GObject.idle_add(self.__settings_win.on_value_found_cb,
                                     self.__settings_win.device_settings['devid'],
                                     user_name, store_name, active))
        job.connect('device-finding-end',
                    lambda job: GObject.idle_add(
                        self.__settings_win.on_finding_end_cb,
                        self.__settings_win.device_settings['devid']))
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
            logger.info("Looking for resolution of device [%s]" % (self.__devid))
            device = pyinsane.Scanner(name=self.__devid)
            sys.stdout.flush()
            resolutions = device.options['resolution'].constraint
            logger.info("Resolutions found: %s" % str(resolutions))
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
        finally:
            self.emit("resolution-finding-end")


GObject.type_register(JobResolutionFinder)


class JobFactoryResolutionFinder(JobFactory):
    def __init__(self, settings_win, selected_resolution, recommended_resolution):
        JobFactory.__init__(self, "ResolutionFinder")
        self.__settings_win = settings_win
        self.__selected_resolution = selected_resolution
        self.__recommended_resolution = recommended_resolution

    def make(self, devid):
        job = JobResolutionFinder(self, next(self.id_generator),
                                  self.__selected_resolution,
                                  self.__recommended_resolution, devid)
        job.connect('resolution-finding-start',
                    lambda job: GObject.idle_add(
                        self.__settings_win.on_finding_start_cb,
                        self.__settings_win.device_settings['resolution']))
        job.connect('resolution-found',
                    lambda job, user_name, store_name, active:
                    GObject.idle_add(
                        self.__settings_win.on_value_found_cb,
                        self.__settings_win.device_settings['resolution'],
                        user_name, store_name, active))
        job.connect('resolution-finding-end',
                    lambda job: GObject.idle_add(
                        self.__settings_win.on_finding_end_cb,
                        self.__settings_win.device_settings['resolution']))
        return job


class JobCalibrationScan(Job):
    __gsignals__ = {
        'calibration-scan-start': (GObject.SignalFlags.RUN_LAST, None,
                                   ()),
        'calibration-scan-done': (GObject.SignalFlags.RUN_LAST, None,
                                  (GObject.TYPE_PYOBJECT,  # Pillow image
                                   GObject.TYPE_INT,  # scan resolution
                                  )),
        'calibration-resize-done': (GObject.SignalFlags.RUN_LAST, None,
                                    (GObject.TYPE_FLOAT,  # resize factor
                                     GObject.TYPE_PYOBJECT, )),  # Pillow image
    }

    can_stop = False
    priority = 495

    def __init__(self, factory, id, resolutions_store, target_viewport, devid):
        Job.__init__(self, factory, id)
        self.__target_viewport = target_viewport
        self.__resolutions_store = resolutions_store
        self.__devid = devid

    def do(self):
        self.emit('calibration-scan-start')

        # find the best resolution : the default calibration resolution
        # is not always available
        resolutions = [x[1] for x in self.__resolutions_store]
        resolutions.sort()

        resolution = PaperworkConfig.DEFAULT_CALIBRATION_RESOLUTION
        for nresolution in resolutions:
            if nresolution > PaperworkConfig.DEFAULT_CALIBRATION_RESOLUTION:
                break
            resolution = nresolution

        logger.info("Will do the calibration scan with a resolution of %d"
                    % resolution)

        # scan
        dev = pyinsane.Scanner(name=self.__devid)
        try:
            # any source is actually fine. we just have a clearly defined
            # preferred order
            set_scanner_opt('source', dev.options['source'],
                            ["Auto", "FlatBed",
                             ".*ADF.*", ".*Feeder.*"])
        except (KeyError, pyinsane.SaneException), exc:
            logger.error("Warning: Unable to set scanner source: %s"
                   % exc)
        try:
            dev.options['resolution'].value = resolution
        except pyinsane.SaneException:
            logger.error("Warning: Unable to set scanner resolution to %d: %s"
                         % (resolution, exc))
        if "Color" in dev.options['mode'].constraint:
            dev.options['mode'].value = "Color"
            logger.info("Scanner mode set to 'Color'")
        elif "Gray" in dev.options['mode'].constraint:
            dev.options['mode'].value = "Gray"
            logger.info("Scanner mode set to 'Gray'")
        else:
            logger.warn("WARNING: Unable to set scanner mode ! May be 'Lineart'")
        maximize_scan_area(dev)
        scan_inst = dev.scan(multiple=False)
        try:
            while True:
                scan_inst.read()
                time.sleep(0)  # Give some CPU time to PyGtk
        except EOFError:
            pass
        orig_img = scan_inst.get_img()
        self.emit('calibration-scan-done', orig_img, resolution)

        # resize
        orig_img_size = orig_img.getbbox()
        orig_img_size = (orig_img_size[2], orig_img_size[3])
        logger.info("Calibration: Got an image of size '%s'"
				% str(orig_img_size))

        target_alloc = self.__target_viewport.get_allocation()
        max_width = target_alloc.width
        max_height = target_alloc.height

        factor_width = (float(max_width) / orig_img_size[0])
        factor_height = (float(max_height) / orig_img_size[1])
        factor = min(factor_width, factor_height)
        if factor > 1.0:
            factor = 1.0

        target_width = int(factor * orig_img_size[0])
        target_height = int(factor * orig_img_size[1])
        target = (target_width, target_height)

        logger.info("Calibration: Will resize it to: (%s) (ratio: %f)"
               % (target, factor))

        resized_img = orig_img.resize(target, PIL.Image.BILINEAR)
        self.emit('calibration-resize-done', factor, resized_img)


GObject.type_register(JobCalibrationScan)


class JobFactoryCalibrationScan(JobFactory):
    def __init__(self, settings_win, target_viewport, resolutions_store):
        JobFactory.__init__(self, "CalibrationScan")
        self.__settings_win = settings_win
        self.__target_viewport = target_viewport
        self.__resolutions_store = resolutions_store

    def make(self, devid):
        job = JobCalibrationScan(self, next(self.id_generator),
                                 self.__resolutions_store,
                                 self.__target_viewport, devid)
        job.connect('calibration-scan-start',
                    lambda job:
                    GObject.idle_add(self.__settings_win.on_scan_start))
        job.connect('calibration-scan-done',
                    lambda job, img, resolution:
                    GObject.idle_add(self.__settings_win.on_scan_done, img,
                                     resolution))
        job.connect('calibration-resize-done',
                    lambda job, factor, img:
                    GObject.idle_add(self.__settings_win.on_resize_done,
                                     factor, img))
        return job


class ActionSelectScanner(SimpleAction):
    def __init__(self, settings_win):
        SimpleAction.__init__(self, "New scanner selected")
        self.__settings_win = settings_win

    def do(self):
        settings = self.__settings_win.device_settings['devid']
        idx = settings['gui'].get_active()
        if idx < 0:
            # happens when the scanner list has been updated
            # but no scanner has been found
            res_settings = self.__settings_win.device_settings['resolution']
            res_settings['stores']['loaded'].clear()
            res_settings['gui'].set_model(res_settings['stores']['loaded'])
            res_settings['gui'].set_sensitive(False)
            self.__settings_win.calibration["scan_button"].set_sensitive(False)
            return
        logger.info("Select scanner: %d" % idx)
        self.__settings_win.calibration["scan_button"].set_sensitive(True)
        devid = settings['stores']['loaded'][idx][1]

        # no point in trying to stop the previous jobs, they are unstoppable
        job = self.__settings_win.job_factories['resolution_finder'].make(devid)
        self.__settings_win.schedulers['main'].schedule(job)


class ActionApplySettings(SimpleAction):
    def __init__(self, settings_win, config):
        SimpleAction.__init__(self, "Apply settings")
        self.__settings_win = settings_win
        self.__config = config

    def do(self):
        need_reindex = False
        workdir = self.__settings_win.workdir_chooser.get_current_folder()
        if workdir != self.__config.workdir:
            self.__config.workdir = workdir
            need_reindex = True

        setting = self.__settings_win.device_settings['devid']
        idx = setting['gui'].get_active()
        if idx >= 0:
            devid = setting['stores']['loaded'][idx][1]
            self.__config.scanner_devid = devid

        setting = self.__settings_win.device_settings['resolution']
        idx = setting['gui'].get_active()
        if idx >= 0:
            resolution = setting['stores']['loaded'][idx][1]
            self.__config.scanner_resolution = resolution

        setting = self.__settings_win.ocr_settings['lang']
        idx = setting['gui'].get_active()
        if idx >= 0:
            lang = setting['store'][idx][1]
            self.__config.ocr_lang = lang

        if self.__settings_win.grips is not None:
            coords = self.__settings_win.grips.get_coords()
            self.__config.scanner_calibration = (
                self.__settings_win.calibration['resolution'], coords)

        self.__config.write()

        self.__settings_win.hide()

        if need_reindex:
            self.__settings_win.emit("need-reindex")


class ActionCancelSettings(SimpleAction):
    def __init__(self, settings_win, config):
        SimpleAction.__init__(self, "Cancel settings")
        self.__settings_win = settings_win
        self.__config = config

    def do(self):
        self.__settings_win.display_config(self.__config)
        self.__settings_win.hide()


class ActionScanCalibration(SimpleAction):
    def __init__(self, settings_win):
        SimpleAction.__init__(self, "Scan calibration sheet")
        self.__settings_win = settings_win

    def do(self):
        setting = self.__settings_win.device_settings['devid']
        idx = setting['gui'].get_active()
        assert(idx >= 0)
        devid = setting['stores']['loaded'][idx][1]

        job = self.__settings_win.job_factories['scan'].make(devid)
        self.__settings_win.schedulers['main'].schedule(job)


class SettingsWindow(GObject.GObject):
    """
    Settings window.
    """

    __gsignals__ = {
        'need-reindex': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, main_scheduler, mainwindow_gui, config):
        GObject.GObject.__init__(self)

        self.schedulers = {
            'main': main_scheduler,
            'progress': JobScheduler('progress'),
        }
        self.local_schedulers = [
            self.schedulers['progress'],
        ]

        widget_tree = load_uifile("settingswindow.glade")

        self.window = widget_tree.get_object("windowSettings")
        self.window.set_transient_for(mainwindow_gui)

        self.__config = config

        self.workdir_chooser = widget_tree.get_object("filechooserbutton")

        actions = {
            "apply": (
                [widget_tree.get_object("buttonSettingsOk")],
                ActionApplySettings(self, config)
            ),
            "cancel": (
                [widget_tree.get_object("buttonSettingsCancel")],
                ActionCancelSettings(self, config)
            ),
            "select_scanner": (
                [widget_tree.get_object("comboboxDevices")],
                ActionSelectScanner(self)
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
                    'loading': widget_tree.get_object("liststoreLoading"),
                    'loaded': widget_tree.get_object("liststoreDevice"),
                },
                'nb_elements': 0,
                'active_idx': -1,
            },
            "resolution": {
                'gui': widget_tree.get_object("comboboxResolution"),
                'stores': {
                    'loading': widget_tree.get_object("liststoreLoading"),
                    'loaded': widget_tree.get_object("liststoreResolution"),
                },
                'nb_elements': 0,
                'active_idx': -1,
            },
        }

        self.ocr_settings = {
            "lang": {
                'gui': widget_tree.get_object("comboboxLang"),
                'store': widget_tree.get_object("liststoreOcrLang"),
            }
        }

        self.calibration = {
            "scan_button": widget_tree.get_object("buttonScanCalibration"),
            "image_gui": widget_tree.get_object("imageCalibration"),
            "image_viewport": widget_tree.get_object("viewportCalibration"),
            "images": [],  # array of tuples: (resize factor, PIL image)
            "image_eventbox": widget_tree.get_object("eventboxCalibration"),
            "image_scrollbars":
            widget_tree.get_object("scrolledwindowCalibration"),
            "resolution":
            PaperworkConfig.DEFAULT_CALIBRATION_RESOLUTION,
        }

        self.grips = None

        self.progressbar = widget_tree.get_object("progressbarScan")
        self.__scan_start = 0.0

        self.job_factories = {
            "device_finder": JobFactoryDeviceFinder(self, config.scanner_devid),
            "resolution_finder": JobFactoryResolutionFinder(self,
                config.scanner_resolution,
                config.RECOMMENDED_RESOLUTION),
            "scan": JobFactoryCalibrationScan(
                self,
                self.calibration['image_viewport'],
                self.device_settings['resolution']['stores']['loaded']
            ),
            "progress_updater": JobFactoryProgressUpdater(self.progressbar),
        }

        ocr_tools = pyocr.get_available_tools()
        if len(ocr_tools) <= 0:
            ocr_langs = []
        else:
            ocr_langs = ocr_tools[0].get_available_languages()
        ocr_langs = self.__get_short_to_long_langs(ocr_langs)
        ocr_langs.sort(key=lambda lang: lang[1])
        ocr_langs.insert(0, (None, _("Disable OCR")))

        self.ocr_settings['lang']['store'].clear()
        for (short_lang, long_lang) in ocr_langs:
            self.ocr_settings['lang']['store'].append([long_lang, short_lang])

        action_names = [
            "apply", "cancel", "select_scanner", "scan_calibration"
        ]
        for action in action_names:
            actions[action][1].connect(actions[action][0])

        self.window.connect("destroy", self.__on_destroy)

        self.display_config(config)

        self.window.set_visible(True)

        # Must be connected after the window has been displayed.
        # Otherwise, if "disable OCR" is already selected in the config
        # it will display a warning popup even before the dialog has been
        # displayed
        self.ocr_settings['lang']['gui'].connect(
            "changed", self.__on_ocr_lang_changed)

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
                if extra != "" and (extra[0] == "-" or extra[0] == "_"):
                    extra = extra[1:]
                try:
                    country = pycountry.languages.get(terminology=short_lang)
                except KeyError:
                    country = pycountry.languages.get(bibliographic=short_lang)
                long_lang = country.name
                if extra != "":
                    long_lang += " (%s)" % (extra)
                langs.append((short_lang, long_lang))
            except KeyError, exc:
                logger.error("Warning: Long name not found for language "
                        "'%s'." % short_lang)
                logger.warn("  Will use short name as long name.")
                langs.append((short_lang, short_lang))
        return langs

    def __on_ocr_lang_changed(self, combobox):
        idx = self.ocr_settings['lang']['gui'].get_active()
        lang = self.ocr_settings['lang']['store'][idx][1]
        if lang is None:
            msg = _("Without OCR, Paperwork will not be able to guess"
                    " automatically page orientation")
            dialog = Gtk.MessageDialog(self.window,
                                       flags=Gtk.DialogFlags.MODAL,
                                       type=Gtk.MessageType.WARNING,
                                       buttons=Gtk.ButtonsType.OK,
                                       message_format=msg)
            dialog.run()
            dialog.destroy()

    def on_finding_start_cb(self, settings):
        settings['gui'].set_sensitive(False)
        settings['gui'].set_model(settings['stores']['loading'])
        settings['gui'].set_active(0)
        settings['stores']['loaded'].clear()
        settings['nb_elements'] = 0
        settings['active_idx'] = -1

    def on_device_finding_start_cb(self):
        self.calibration["scan_button"].set_sensitive(False)
        self.on_finding_start_cb(self.device_settings['devid'])
        for element in self.device_settings.values():
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

    def set_mouse_cursor(self, cursor):
        self.window.get_window().set_cursor({
            "Normal": None,
            "Busy": Gdk.Cursor.new(Gdk.CursorType.WATCH),
        }[cursor])

    def on_scan_start(self):
        self.calibration["scan_button"].set_sensitive(False)
        self.set_mouse_cursor("Busy")
        self.calibration['image_gui'].set_alignment(0.5, 0.5)
        self.calibration['image_gui'].set_from_stock(
            Gtk.STOCK_EXECUTE, Gtk.IconSize.DIALOG)

        self.__scan_start = time.time()

        self.__scan_progress_job = self.job_factories['progress_updater'].make(
            value_min=0.0, value_max=1.0,
            total_time=self.__config.scan_time['calibration'])
        self.schedulers['progress'].schedule(self.__scan_progress_job)

    def on_scan_done(self, img, scan_resolution):
        scan_stop = time.time()
        self.schedulers['progress'].cancel(self.__scan_progress_job)
        self.__config.scan_time['calibration'] = scan_stop - self.__scan_start

        self.calibration['images'] = [(1.0, img)]
        self.calibration['resolution'] = scan_resolution
        self.progressbar.set_fraction(0.0)

    def on_resize_done(self, factor, img):
        self.calibration['images'].insert(0, (factor, img))
        self.grips = ImgGripHandler(self.calibration['images'],
                                    self.calibration['image_scrollbars'],
                                    self.calibration['image_eventbox'],
                                    self.calibration['image_gui'])
        self.grips.visible = True
        self.set_mouse_cursor("Normal")
        self.calibration["scan_button"].set_sensitive(True)

    def display_config(self, config):
        self.workdir_chooser.set_current_folder(config.workdir)
        idx = 0
        current_ocr_lang = config.ocr_lang
        for (long_lang, short_lang) in self.ocr_settings['lang']['store']:
            if short_lang == current_ocr_lang:
                self.ocr_settings['lang']['gui'].set_active(idx)
            idx += 1

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
