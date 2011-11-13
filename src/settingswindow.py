"""
Settings window.
"""

import gtk
import os

from util import load_uifile


class SettingsWindow(object):
    """
    Settings window.
    """
    OCR_LANGS = {
        "deu": "German",
        "eng": "English",
        "fra": "French",
        "ita": "Italian",
        "nld": "Dutch",
        "port": "Portuguese",
        "spa": "Spanish",
        "vie": "Vietnamese",
    }
    OCR_LANGS_REVERSE = dict((value, keyword) \
                             for keyword, value in OCR_LANGS.iteritems())

    def __init__(self, mainwindow, config, scanner_mgmt):
        self.__mainwindow = mainwindow
        self.__config = config

        self.__possible_scanners = scanner_mgmt.available_devices
        self.__selected_scanner = self.__config.scanner_devid
        self.__possible_resolutions = scanner_mgmt.POSSIBLE_RESOLUTIONS
        self.__selected_resolution = self.__config.scanner_resolution
        self.__recommended_resolution = scanner_mgmt.RECOMMENDED_RESOLUTION

        self.__widget_tree = load_uifile("settingswindow.glade")

        self.__settings_win = self.__widget_tree.get_object("windowSettings")
        self.__settings_win.set_transient_for(mainwindow.main_window)
        assert(self.__settings_win)

        self.__ocrlangs_widget = None
        self.__scanner_device_widget = None
        self.__scanner_resolution_widget = None

        self.__connect_signals()
        self.__fill_in_form()
        self.__settings_win.set_visible(True)

    @staticmethod
    def __dev_to_dev_name(dev):
        return ("%s %s (%s)" % (dev[1], dev[2], dev[3]))

    @staticmethod
    def __resolution_to_resolution_name(resolution, recommended):
        txt = ("%d dpi" % (resolution))
        if (resolution == recommended):
            txt += " (recommended)" # TODO(Jflesch): i18n / l10n
        return txt

    def __get_selected_device(self):
        txt = self.__scanner_device_widget.get_active_text()
        for dev in self.__possible_scanners:
            if self.__dev_to_dev_name(dev) == txt:
                return dev[0]
        return None

    def __get_selected_resolution(self):
        txt = self.__scanner_resolution_widget.get_active_text()
        for resolution in self.__possible_resolutions:
            if (self.__resolution_to_resolution_name(resolution,
                    self.__recommended_resolution) == txt):
                return resolution
        return None

    def __apply(self):
        """
        Apply new user settings.
        """
        assert(self.__ocrlangs_widget)
        assert(self.__possible_scanners != None)

        need_reindex = False

        try:
            os.makedirs(self.__widget_tree \
                    .get_object("filechooserbutton").get_current_folder())
        except OSError:
            pass

        self.__config.ocrlang = \
                self.OCR_LANGS_REVERSE[
                    self.__ocrlangs_widget.get_active_text()]

        if self.__get_selected_device() != None:
            self.__config.scanner_devid = self.__get_selected_device()
        self.__config.scanner_resolution = self.__get_selected_resolution()

        if self.__config.workdir != \
                self.__widget_tree.get_object("filechooserbutton") \
                        .get_current_folder():
            self.__config.workdir = \
                    self.__widget_tree.get_object("filechooserbutton") \
                        .get_current_folder()
            need_reindex = True

        self.__mainwindow.update_scanner_settings()
        self.__mainwindow.update_buttons_state()

        if need_reindex:
            self.__mainwindow.new_document()
            self.__mainwindow.reindex()
        self.__destroy()
        self.__config.write()
        return True

    def __connect_signals(self):
        """
        Connect the GTK signals of the settings window.
        """
        self.__settings_win.connect("destroy", lambda x: self.__destroy())
        self.__widget_tree.get_object("buttonSettingsCancel").connect(
                "clicked", lambda x: self.__destroy())
        self.__widget_tree.get_object("buttonSettingsOk").connect(
                "clicked", lambda x: self.__apply())

    def __fill_in_form(self):
        """
        Use the values from the Paperwork configuration to fill in the settings
        window.
        """
        # work dir
        self.__widget_tree.get_object("filechooserbutton").set_current_folder(
            self.__config.workdir)

        # ocr lang
        ocr_table = self.__widget_tree.get_object("tableOCRSettings")
        assert(ocr_table)
        self.__ocrlangs_widget = gtk.combo_box_new_text()
        idx = 0
        active_idx = 0
        for (shortname, longname) in self.OCR_LANGS.items():
            self.__ocrlangs_widget.append_text(longname)
            if shortname == self.__config.ocrlang:
                active_idx = idx
            idx = idx + 1
        self.__ocrlangs_widget.set_active(active_idx)
        self.__ocrlangs_widget.set_visible(True)
        ocr_table.attach(self.__ocrlangs_widget,
                         1, # left_attach
                         2, # right_attach
                         0, # top_attach
                         1, # bottom_attach
                         xoptions=gtk.EXPAND|gtk.FILL)

        scanner_table = self.__widget_tree.get_object("tableScannerSettings")
        assert(scanner_table)

        # scanner devices
        self.__scanner_device_widget = gtk.combo_box_new_text()
        idx = 0
        active_idx = 0
        for dev in self.__possible_scanners:
            self.__scanner_device_widget.append_text(
                    self.__dev_to_dev_name(dev))
            if dev[0] == self.__selected_scanner:
                active_idx = idx
            idx = idx + 1
        self.__scanner_device_widget.set_active(active_idx)
        self.__scanner_device_widget.set_visible(True)
        scanner_table.attach(self.__scanner_device_widget,
                             1, # left_attach
                             2, # right_attach
                             0, # top_attach
                             1, # bottom_attach
                             xoptions=gtk.EXPAND|gtk.FILL)

        # scanner resolution
        self.__scanner_resolution_widget = gtk.combo_box_new_text()
        idx = 0
        active_idx = 0
        for resolution in self.__possible_resolutions:
            self.__scanner_resolution_widget.append_text(
                    self.__resolution_to_resolution_name(resolution,
                            self.__recommended_resolution))
            if resolution == self.__selected_resolution:
                active_idx = idx
            idx = idx + 1
        self.__scanner_resolution_widget.set_active(active_idx)
        self.__scanner_resolution_widget.set_visible(True)
        scanner_table.attach(self.__scanner_resolution_widget,
                             1, # left_attach
                             2, # right_attach
                             1, # top_attach
                             2, # bottom_attach
                             xoptions=gtk.EXPAND|gtk.FILL)

    def __destroy(self):
        """
        Hide and destroy the settings window.
        """
        self.__widget_tree.get_object("windowSettings").destroy()
