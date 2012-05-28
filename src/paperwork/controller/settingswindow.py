"""
Settings window.
"""

import Image
import ImageDraw
import os
import sys
import time

import gettext
import gobject
import gtk
import pycountry
import pyocr.pyocr as pyocr

import pyinsane.abstract_th as pyinsane

from paperwork.controller.actions import SimpleAction
from paperwork.controller.workers import Worker
from paperwork.util import image2pixbuf
from paperwork.util import load_uifile

_ = gettext.gettext

RECOMMENDED_RESOLUTION = 300


class WorkerDeviceFinder(Worker):
    __gsignals__ = {
        'device-finding-start' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                                  ()),
        'device-found' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                          (gobject.TYPE_STRING,  # user name
                           gobject.TYPE_STRING,  # device id
                           gobject.TYPE_BOOLEAN)  # is the active one
                         ),
        'device-finding-end' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
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
            # HACK(Jflesch): Using sane C binding obviously freeze Gobject/Gtk
            # so we give it a little time to display/refresh the settings win
            time.sleep(1)
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


gobject.type_register(WorkerDeviceFinder)


class WorkerResolutionFinder(Worker):
    __gsignals__ = {
        'resolution-finding-start' : (gobject.SIGNAL_RUN_LAST,
                                      gobject.TYPE_NONE, ()),
        'resolution-found' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                              (gobject.TYPE_STRING,  # user name
                               gobject.TYPE_INT,  # resolution value
                               gobject.TYPE_BOOLEAN)  # is the active one
                              ),
        'resolution-finding-end' : (gobject.SIGNAL_RUN_LAST,
                                    gobject.TYPE_NONE, ())
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
            # HACK(Jflesch): Using sane C binding obviously freeze Gobject/Gtk
            # so we give it a little time to display/refresh the settings win
            time.sleep(1)

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


gobject.type_register(WorkerResolutionFinder)


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
            self.__settings_win.scan_button.set_sensitive(False)
            return
        print "Select scanner: %d" % idx
        self.__settings_win.scan_button.set_sensitive(True)
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
            self.__config.scanner_devid = resolution

        setting = self.__settings_win.ocr_settings['lang']
        idx = setting['gui'].get_active()
        if idx >= 0:
            lang = setting['store'][idx][1]
            self.__config.ocrlang = lang

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
        # TODO
        pass


class SettingsWindow(gobject.GObject):
    """
    Settings window.
    """

    __gsignals__ = {
        'need-reindex' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    def __init__(self, mainwindow_gui, config):
        gobject.GObject.__init__(self)
        widget_tree = load_uifile("settingswindow.glade")

        self.window = widget_tree.get_object("windowSettings")
        self.window.set_transient_for(mainwindow_gui)

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

        self.scan_button = widget_tree.get_object("buttonScanCalibration")

        self.workers = {
            "device_finder" : WorkerDeviceFinder(config.scanner_devid),
            "resolution_finder" : WorkerResolutionFinder(
                    config.scanner_resolution,
                    config.RECOMMENDED_RESOLUTION),
        }

        ocr_tools = pyocr.get_available_tools()
        if len(ocr_tools) <= 0:
            ocr_langs = []
        else:
            ocr_langs = ocr_tools[0].get_available_languages()
        ocr_langs = self.__get_short_to_long_langs(ocr_langs)
        self.ocr_settings['lang']['store'].clear()
        for (short_lang, long_lang) in ocr_langs.iteritems():
            self.ocr_settings['lang']['store'].append([long_lang, short_lang])

        for action in ["apply", "cancel", "select_scanner", "scan_calibration"]:
            actions[action][1].connect(actions[action][0])

        self.workers['device_finder'].connect(
                'device-finding-start',
                lambda worker: gobject.idle_add(
                    self.__on_device_finding_start_cb))
        self.workers['device_finder'].connect(
                'device-found',
                lambda worker, user_name, store_name, active: \
                    gobject.idle_add(self.__on_value_found_cb,
                                     self.device_settings['devid'],
                                     user_name, store_name, active))
        self.workers['device_finder'].connect(
                'device-finding-end',
                lambda worker: gobject.idle_add(
                    self.__on_finding_end_cb,
                    self.device_settings['devid']))

        self.workers['resolution_finder'].connect(
                'resolution-finding-start',
                lambda worker: gobject.idle_add(
                    self.__on_finding_start_cb,
                    self.device_settings['resolution']))
        self.workers['resolution_finder'].connect(
                'resolution-found',
                lambda worker, user_name, store_name, active: \
                    gobject.idle_add(self.__on_value_found_cb,
                                     self.device_settings['resolution'],
                                     user_name, store_name, active))
        self.workers['resolution_finder'].connect(
                'resolution-finding-end',
                lambda worker: gobject.idle_add(
                    self.__on_finding_end_cb,
                    self.device_settings['resolution']))

        self.display_config(config)

        self.window.set_visible(True)

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
            A dictionnary: Keys are the short languages name, values are the
            corresponding long languages names.
        """
        long_langs = {}
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
                long_langs[short_lang] = long_lang
            except KeyError, exc:
                print ("Warning: Long name not found for language '%s'."
                       % (short_lang))
                print ("  Exception was: %s" % (str(exc)))
                print ("  Will use short name as long name.")
                long_langs[short_lang] = short_lang
        return long_langs

    def __on_finding_start_cb(self, settings):
        settings['gui'].set_sensitive(False)
        settings['gui'].set_model(settings['stores']['loading'])
        settings['gui'].set_active(0)
        settings['stores']['loaded'].clear()
        settings['nb_elements'] = 0
        settings['active_idx'] = -1

    def __on_device_finding_start_cb(self):
        self.scan_button.set_sensitive(False)
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

    def display_config(self, config):
        self.workdir_chooser.set_current_folder(config.workdir)
        idx = 0
        for (long_lang, short_lang) in self.ocr_settings['lang']['store']:
            if short_lang == config.ocrlang:
                self.ocr_settings['lang']['gui'].set_active(idx)
            idx += 1

    def hide(self):
        """
        Hide and destroy the settings window.
        """
        for worker in self.workers.values():
            worker.stop()
        self.window.destroy()

gobject.type_register(SettingsWindow)
