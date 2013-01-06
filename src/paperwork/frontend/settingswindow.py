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

import Image
import ImageDraw
import os
import sys
import time

import gettext
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk
import pycountry
import pyocr.pyocr as pyocr

import pyinsane.abstract_th as pyinsane

from paperwork.backend.config import PaperworkConfig
from paperwork.frontend.actions import SimpleAction
from paperwork.frontend.workers import Worker
from paperwork.frontend.workers import WorkerProgressUpdater
from paperwork.util import image2pixbuf
from paperwork.util import load_uifile

_ = gettext.gettext

RECOMMENDED_RESOLUTION = 300


class CalibrationGrip(object):
    """
    Represents one of the grip that user can move to calibrate its scanner.
    """
    GRIP_SIZE = 20
    COLOR = (0x00, 0x00, 0xFF)

    def __init__(self, pos_x, pos_y):
        self.position = (int(pos_x), int(pos_y))

    def draw(self, img, imgdraw, ratio):
        """
        Draw the grip on the image

        Arguments:
            imgdraw --- drawing area
            ratio --- Scale at which the image is represented
        """
        bbox = img.getbbox()
        img_x = bbox[2] / ratio
        img_y = bbox[3] / ratio
        (pos_x, pos_y) = self.position
        # fix our position in case we are out the image
        if pos_x < 0:
            pos_x = 0
        if pos_x >= img_x:
            pos_x = img_x - 1
        if pos_y < 0:
            pos_y = 0
        if pos_y >= img_y:
            pos_y = img_y
        self.position = (pos_x, pos_y)
        pos_x = int(ratio * pos_x)
        pos_y = int(ratio * pos_y)
        imgdraw.rectangle(((pos_x - self.GRIP_SIZE, pos_y - self.GRIP_SIZE),
                           (pos_x + self.GRIP_SIZE, pos_y + self.GRIP_SIZE)),
                          outline=self.COLOR)

    def is_on_grip(self, position, ratio):
        """
        Indicates if position is on the grip

        Arguments:
            position --- tuple (int, int)
            ratio --- Scale at which the image is represented

        Returns:
            True or False
        """
        x_min = int(ratio * self.position[0]) - self.GRIP_SIZE
        y_min = int(ratio * self.position[1]) - self.GRIP_SIZE
        x_max = int(ratio * self.position[0]) + self.GRIP_SIZE
        y_max = int(ratio * self.position[1]) + self.GRIP_SIZE
        return (x_min <= position[0] and position[0] <= x_max
            and y_min <= position[1] and position[1] <= y_max)


class CalibrationGripHandler(object):
    def __init__(self, config, settings_win):
        self.__settings_win = settings_win

        calibration = config.scanner_calibration
        if calibration == None:
            self.__grips = None
        else:
            self.__grips = (CalibrationGrip(calibration[0][0],
                                            calibration[0][1]),
                            CalibrationGrip(calibration[1][0],
                                            calibration[1][1]))
        self.selected = None

    def on_mouse_button_pressed_cb(self, event):
        if self.__grips == None:
            return

        (mouse_x, mouse_y) = event.get_coords()
        factor = self.__settings_win.calibration['images'][0][0]

        self.selected = None
        for grip in self.__grips:
            if grip.is_on_grip((mouse_x, mouse_y), factor):
                self.selected = grip
                break

    def on_mouse_motion(self, event):
        if self.__grips == None:
            return
        if len(self.__settings_win.calibration['images']) <= 0:
            return

        (mouse_x, mouse_y) = event.get_coords()
        factor = self.__settings_win.calibration['images'][0][0]

        if self.selected:
            is_on_grip = True
        else:
            is_on_grip = False
            for grip in self.__grips:
                if grip.is_on_grip((mouse_x, mouse_y), factor):
                    is_on_grip = True
                    break

        if is_on_grip:
            cursor = Gdk.Cursor.new(Gdk.CursorType.TCROSS)
        else:
            cursor = Gdk.Cursor.new(Gdk.CursorType.HAND1)
        self.__settings_win.calibration['image_gui'].get_window().set_cursor(cursor)

    def __move_grip(self, event_pos):
        """
        Move a grip, based on the position
        """
        (mouse_x, mouse_y) = event_pos
        (factor, img) = self.__settings_win.calibration['images'][0]

        if not self.selected:
            return None

        new_x = mouse_x / factor
        new_y = mouse_y / factor
        self.selected.position = (new_x, new_y)
        self.__settings_win.redraw_calibration_image()

    def on_mouse_button_released_cb(self, event):
        if self.__grips == None:
            return

        self.__move_grip(event.get_coords())
        if self.selected:
            self.selected = None
        else:
            self.__settings_win.switch_calibration_img_scale()

    def draw(self, img, imgdraw, factor):
        if self.__grips == None:
            bbox = img.getbbox()
            self.__grips = (
                CalibrationGrip(0, 0),
                CalibrationGrip(bbox[2] / factor, bbox[3] / factor))
        for grip in self.__grips:
            grip.draw(img, imgdraw, factor)
        a = (int(factor * self.__grips[0].position[0]),
             int(factor * self.__grips[0].position[1]))
        b = (int(factor * self.__grips[1].position[0]),
             int(factor * self.__grips[1].position[1]))
        imgdraw.rectangle((a, b), outline=CalibrationGrip.COLOR)

    def has_coords(self):
        return self.__grips != None

    def get_coords(self):
        return ((int(self.__grips[0].position[0]),
                 int(self.__grips[0].position[1])),
                (int(self.__grips[1].position[0]),
                 int(self.__grips[1].position[1])))


class WorkerDeviceFinder(Worker):
    __gsignals__ = {
        'device-finding-start' : (GObject.SignalFlags.RUN_LAST, None,
                                  ()),
        'device-found' : (GObject.SignalFlags.RUN_LAST, None,
                          (GObject.TYPE_STRING,  # user name
                           GObject.TYPE_STRING,  # device id
                           GObject.TYPE_BOOLEAN)  # is the active one
                         ),
        'device-finding-end' : (GObject.SignalFlags.RUN_LAST, None, ())
    }

    can_interrupt = False

    def __init__(self, selected_devid):
        Worker.__init__(self, "Device finder")
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
            print "Looking for scan devices ..."
            sys.stdout.flush()
            devices = pyinsane.get_devices()
            for device in devices:
                selected = (self.__selected_devid == device.name)
                name = self.__get_dev_name(device)
                print "Device found: [%s] -> [%s]" % (name, device.name)
                sys.stdout.flush()
                self.emit('device-found', name, device.name, selected)
        finally:
            self.emit("device-finding-end")


GObject.type_register(WorkerDeviceFinder)


class WorkerResolutionFinder(Worker):
    __gsignals__ = {
        'resolution-finding-start' : (GObject.SignalFlags.RUN_LAST,
                                      None, ()),
        'resolution-found' : (GObject.SignalFlags.RUN_LAST, None,
                              (GObject.TYPE_STRING,  # user name
                               GObject.TYPE_INT,  # resolution value
                               GObject.TYPE_BOOLEAN)  # is the active one
                              ),
        'resolution-finding-end' : (GObject.SignalFlags.RUN_LAST,
                                    None, ())
    }

    can_interrupt = False

    def __init__(self, selected_resolution,
                 recommended_resolution):
        Worker.__init__(self, "Resolution finder")
        self.__selected_resolution = selected_resolution
        self.__recommended_resolution = recommended_resolution

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

    def do(self, devid):
        self.emit("resolution-finding-start")
        try:
            print "Looking for resolution of device [%s]" % (devid)
            device = pyinsane.Scanner(name=devid)
            sys.stdout.flush()
            resolutions = device.options['resolution'].constraint
            print "Resolutions found: %s" % (str(resolutions))
            sys.stdout.flush()
            # Sometimes sane return the resolutions as a integer array,
            # sometimes as a range (-> tuple). So if it is a range, we turn
            # it into an array
            if isinstance(resolutions, tuple):
                res_array = []
                for res in range(resolutions[0], resolutions[1] + 1,
                                 resolutions[2]):
                    res_array.append(res)
                resolutions = res_array

            for resolution in resolutions:
                name = self.__get_resolution_name(resolution)
                self.emit('resolution-found', name, resolution,
                          (resolution == self.__selected_resolution))
        finally:
            self.emit("resolution-finding-end")


GObject.type_register(WorkerResolutionFinder)


class WorkerCalibrationScan(Worker):
    __gsignals__ = {
        'calibration-scan-start' : (GObject.SignalFlags.RUN_LAST, None,
                                    ()),
        'calibration-scan-done' : (GObject.SignalFlags.RUN_LAST, None,
                                   (GObject.TYPE_PYOBJECT, )  # PIL image
                                  ),
        'calibration-resize-done' : (GObject.SignalFlags.RUN_LAST, None,
                                     (GObject.TYPE_FLOAT, # resize factor
                                      GObject.TYPE_PYOBJECT, ) # PIL image
                                    ),
    }

    can_interrupt = True

    def __init__(self, target_viewport):
        Worker.__init__(self, "Calibration scan")
        self.target_viewport = target_viewport

    def do(self, devid):
        self.emit('calibration-scan-start')

        # scan
        dev = pyinsane.Scanner(name=devid)
        try:
            dev.options['source'].value = "Auto"
        except pyinsane.rawapi.SaneException, exc:
            print ("Warning: Unable to set scanner source to 'Auto': %s" %
                   (str(exc)))
        try:
            dev.options['resolution'].value = \
                    PaperworkConfig.CALIBRATION_RESOLUTION
        except pyinsane.rawapi.SaneException:
            print ("Warning: Unable to set scanner resolution to %d: %s" %
                   (PaperworkConfig.CALIBRATION_RESOLUTION, str(exc)))

        scan_inst = dev.scan(multiple=False)
        try:
            while self.can_run:
                scan_inst.read()
                time.sleep(0)  # Give some CPU time to PyGtk
        except EOFError:
            pass
        if not self.can_run:
            return
        orig_img = scan_inst.get_img()
        self.emit('calibration-scan-done', orig_img)

        # resize
        orig_img_size = orig_img.getbbox()
        orig_img_size = (orig_img_size[2], orig_img_size[3])
        print "Calibration: Got an image of size '%s'" % (str(orig_img_size))

        target_alloc = self.target_viewport.get_allocation()
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

        print ("Calibration: Will resize it to: (%s) (ratio: %f)"
               % (str(target), factor))

        resized_img = orig_img.resize(target, Image.BILINEAR)
        self.emit('calibration-resize-done', factor, resized_img)


GObject.type_register(WorkerCalibrationScan)


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
        print "Select scanner: %d" % idx
        self.__settings_win.calibration["scan_button"].set_sensitive(True)
        devid = settings['stores']['loaded'][idx][1]
        self.__settings_win.workers['resolution_finder'].start(devid=devid)


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
            self.__config.ocrlang = lang

        if self.__settings_win.grips.has_coords():
            self.__config.scanner_calibration = \
                    self.__settings_win.grips.get_coords()

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
        self.__settings_win.workers['scan'].start(devid=devid)


class SettingsWindow(GObject.GObject):
    """
    Settings window.
    """

    __gsignals__ = {
        'need-reindex' : (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, mainwindow_gui, config):
        GObject.GObject.__init__(self)
        widget_tree = load_uifile("settingswindow.glade")

        self.window = widget_tree.get_object("windowSettings")
        self.window.set_transient_for(mainwindow_gui)

        self.__config = config

        self.workdir_chooser = widget_tree.get_object("filechooserbutton")

        actions = {
            "apply" : (
                [widget_tree.get_object("buttonSettingsOk")],
                ActionApplySettings(self, config)
            ),
            "cancel" : (
                [widget_tree.get_object("buttonSettingsCancel")],
                ActionCancelSettings(self, config)
            ),
            "select_scanner" : (
                [widget_tree.get_object("comboboxDevices")],
                ActionSelectScanner(self)
            ),
            "scan_calibration" : (
                [widget_tree.get_object("buttonScanCalibration")],
                ActionScanCalibration(self)
            )
        }

        self.device_settings = {
            "devid" : {
                'gui' : widget_tree.get_object("comboboxDevices"),
                'stores' : {
                    'loading' : widget_tree.get_object("liststoreLoading"),
                    'loaded'  : widget_tree.get_object("liststoreDevice"),
                },
                'nb_elements' : 0,
                'active_idx' : -1,
            },
            "resolution" : {
                'gui' : widget_tree.get_object("comboboxResolution"),
                'stores' : {
                    'loading' : widget_tree.get_object("liststoreLoading"),
                    'loaded' : widget_tree.get_object("liststoreResolution"),
                },
                'nb_elements' : 0,
                'active_idx' : -1,
            },
        }

        self.ocr_settings = {
            "lang" : {
                'gui' : widget_tree.get_object("comboboxLang"),
                'store' : widget_tree.get_object("liststoreOcrLang"),
            }
        }

        self.calibration = {
            "scan_button" : widget_tree.get_object("buttonScanCalibration"),
            "image_gui" : widget_tree.get_object("imageCalibration"),
            "image_viewport" : widget_tree.get_object("viewportCalibration"),
            "images" : [],  # array of tuples : (resize factor, PIL image)
            "image_eventbox" : widget_tree.get_object("eventboxCalibration"),
            "image_scrollbars" : widget_tree.get_object("scrolledwindowCalibration"),
        }

        self.grips = CalibrationGripHandler(config, self)

        self.progressbar = widget_tree.get_object("progressbarScan")
        self.__scan_start = 0.0

        self.workers = {
            "device_finder" : WorkerDeviceFinder(config.scanner_devid),
            "resolution_finder" : WorkerResolutionFinder(
                    config.scanner_resolution,
                    config.RECOMMENDED_RESOLUTION),
            "scan" : WorkerCalibrationScan(
                    self.calibration['image_viewport']),
            "progress_updater" : WorkerProgressUpdater("calibration scan",
                                                       self.progressbar)
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

        for action in ["apply", "cancel", "select_scanner", "scan_calibration"]:
            actions[action][1].connect(actions[action][0])

        self.workers['device_finder'].connect(
                'device-finding-start',
                lambda worker: GObject.idle_add(
                    self.__on_device_finding_start_cb))
        self.workers['device_finder'].connect(
                'device-found',
                lambda worker, user_name, store_name, active: \
                    GObject.idle_add(self.__on_value_found_cb,
                                     self.device_settings['devid'],
                                     user_name, store_name, active))
        self.workers['device_finder'].connect(
                'device-finding-end',
                lambda worker: GObject.idle_add(
                    self.__on_finding_end_cb,
                    self.device_settings['devid']))

        self.workers['resolution_finder'].connect(
                'resolution-finding-start',
                lambda worker: GObject.idle_add(
                    self.__on_finding_start_cb,
                    self.device_settings['resolution']))
        self.workers['resolution_finder'].connect(
                'resolution-found',
                lambda worker, user_name, store_name, active: \
                    GObject.idle_add(self.__on_value_found_cb,
                                     self.device_settings['resolution'],
                                     user_name, store_name, active))
        self.workers['resolution_finder'].connect(
                'resolution-finding-end',
                lambda worker: GObject.idle_add(
                    self.__on_finding_end_cb,
                    self.device_settings['resolution']))

        self.workers['scan'].connect('calibration-scan-start',
                lambda worker: GObject.idle_add(self.__on_scan_start))
        self.workers['scan'].connect('calibration-scan-done',
                lambda worker, img: GObject.idle_add(self.__on_scan_done, img))
        self.workers['scan'].connect('calibration-resize-done',
                lambda worker, factor, img: \
                    GObject.idle_add(self.__on_resize_done, factor, img))

        self.calibration['image_eventbox'].connect("button-press-event",
                lambda x, ev: self.grips.on_mouse_button_pressed_cb(ev))
        self.calibration['image_eventbox'].connect("motion-notify-event",
                lambda x, ev: self.grips.on_mouse_motion(ev))
        self.calibration['image_eventbox'].connect("button-release-event",
                lambda x, ev: self.grips.on_mouse_button_released_cb(ev))
        self.calibration['image_eventbox'].add_events(
                Gdk.EventMask.POINTER_MOTION_MASK)

        self.window.connect("destroy", self.__on_destroy)

        self.display_config(config)

        self.window.set_visible(True)

        # Must be connected after the window has been displayed.
        # Otherwise, if "disable OCR" is already selected in the config
        # it will display a warning popup even before the dialog has been
        # displayed
        self.ocr_settings['lang']['gui'].connect(
            "changed", self.__on_ocr_lang_changed)

        self.workers['device_finder'].start()

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
                try:
                    country = pycountry.languages.get(terminology=short_lang[:3])
                except KeyError:
                    country = pycountry.languages.get(bibliographic=short_lang[:3])
                extra = None
                if "_" in short_lang:
                    extra = short_lang.split("_")[1]
                long_lang = country.name
                if extra != None:
                    long_lang += " (%s)" % (extra)
                langs.append((short_lang, long_lang))
            except KeyError, exc:
                print ("Warning: Long name not found for language '%s'."
                       % (short_lang))
                print ("  Exception was: %s" % (str(exc)))
                print ("  Will use short name as long name.")
                langs.append((short_lang, short_lang))
        return langs

    def __on_ocr_lang_changed(self, combobox):
        idx = self.ocr_settings['lang']['gui'].get_active()
        lang = self.ocr_settings['lang']['store'][idx][1]
        if lang == None:
            msg = _("Without OCR, Paperwork will not be able to guess"
                    " automatically page orientation")
            dialog = Gtk.MessageDialog(self.window,
                                       flags=Gtk.DialogFlags.MODAL,
                                       type=Gtk.MessageType.WARNING,
                                       buttons=Gtk.ButtonsType.OK,
                                       message_format=msg)
            dialog.run()
            dialog.destroy()

    def __on_finding_start_cb(self, settings):
        settings['gui'].set_sensitive(False)
        settings['gui'].set_model(settings['stores']['loading'])
        settings['gui'].set_active(0)
        settings['stores']['loaded'].clear()
        settings['nb_elements'] = 0
        settings['active_idx'] = -1

    def __on_device_finding_start_cb(self):
        self.calibration["scan_button"].set_sensitive(False)
        self.__on_finding_start_cb(self.device_settings['devid'])
        for element in self.device_settings.values():
            element['gui'].set_sensitive(False)

    def __on_value_found_cb(self, settings,
                            user_name, store_name, active):
        store_line = [user_name, store_name]
        print "Got value [%s]" % (str(store_line))
        settings['stores']['loaded'].append(store_line)
        if active:
            settings['active_idx'] = settings['nb_elements']
        settings['nb_elements'] += 1

    def __on_finding_end_cb(self, settings):
        settings['gui'].set_sensitive(True)
        settings['gui'].set_model(settings['stores']['loaded'])
        if settings['active_idx'] >= 0:
            settings['gui'].set_active(settings['active_idx'])
        else:
            settings['gui'].set_active(0)

    def set_mouse_cursor(self, cursor):
        self.window.get_window().set_cursor({
            "Normal" : None,
            "Busy" : Gdk.Cursor.new(Gdk.CursorType.WATCH),
        }[cursor])

    def __on_scan_start(self):
        self.calibration["scan_button"].set_sensitive(False)
        self.set_mouse_cursor("Busy")
        self.calibration['image_gui'].set_alignment(0.5, 0.5)
        self.calibration['image_gui'].set_from_stock(
                Gtk.STOCK_EXECUTE, Gtk.IconSize.DIALOG)

        self.__scan_start = time.time()
        self.workers['progress_updater'].start(value_min=0.0, value_max=1.0,
                total_time=self.__config.scan_time['calibration'])

    def __on_scan_done(self, img):
        scan_stop = time.time()
        self.workers['progress_updater'].soft_stop()
        self.__config.scan_time['calibration'] = scan_stop - self.__scan_start

        self.calibration['images'] = [(1.0, img)]
        self.progressbar.set_fraction(0.0)

    def __on_resize_done(self, factor, img):
        self.calibration['images'].insert(0, (factor, img))
        self.set_mouse_cursor("Normal")
        self.calibration["scan_button"].set_sensitive(True)
        self.calibration['image_gui'].set_alignment(0.0, 0.0)
        self.redraw_calibration_image()

    def redraw_calibration_image(self):
        (factor, img) = self.calibration['images'][0]
        img = img.copy()
        self.grips.draw(img, ImageDraw.Draw(img), factor)
        img = image2pixbuf(img)
        self.calibration['image_gui'].set_from_pixbuf(img)

    def switch_calibration_img_scale(self):
        img = self.calibration['images'].pop(0)
        self.calibration['images'].append(img)
        self.redraw_calibration_image()

    def display_config(self, config):
        self.workdir_chooser.set_current_folder(config.workdir)
        idx = 0
        for (long_lang, short_lang) in self.ocr_settings['lang']['store']:
            if short_lang == config.ocrlang:
                self.ocr_settings['lang']['gui'].set_active(idx)
            idx += 1

    def __on_destroy(self, window=None):
        for worker in self.workers.values():
            worker.stop()
        print "Settings window destroyed"

    def hide(self):
        """
        Hide and destroy the settings window.
        """
        self.window.destroy()

GObject.type_register(SettingsWindow)
