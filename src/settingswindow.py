"""
Settings window.
"""

import Image
import ImageDraw
import gtk
import os

from scanner import PaperworkScanner
from util import image2pixbuf
from util import load_uifile

class CalibrationGrip(object):
    GRIP_SIZE = 20
    COLOR = (0x00, 0x00, 0xFF)

    def __init__(self, pos_x, pos_y):
        self.position = (pos_x, pos_y)
        self.selected = False

    def draw(self, imgdraw, ratio):
        x = int(ratio * self.position[0])
        y = int(ratio * self.position[1])
        imgdraw.rectangle(((x - self.GRIP_SIZE, y - self.GRIP_SIZE),
                           (x + self.GRIP_SIZE, y + self.GRIP_SIZE)),
                          outline=self.COLOR)

    def is_on_grip(self, position, ratio):
        x_min = int(ratio * self.position[0]) - self.GRIP_SIZE
        y_min = int(ratio * self.position[1]) - self.GRIP_SIZE
        x_max = int(ratio * self.position[0]) + self.GRIP_SIZE
        y_max = int(ratio * self.position[1]) + self.GRIP_SIZE
        return (x_min <= position[0] and position[0] <= x_max
            and y_min <= position[1] and position[1] <= y_max)

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

        self.__scanner_mgmt = scanner_mgmt
        self.__possible_scanners = scanner_mgmt.available_devices
        self.__selected_scanner = self.__config.scanner_devid
        self.__possible_resolutions = []
        self.__selected_resolution = self.__config.scanner_resolution
        self.__recommended_resolution = scanner_mgmt.RECOMMENDED_RESOLUTION

        self.__widget_tree = load_uifile("settingswindow.glade")

        self.__settings_win = self.__widget_tree.get_object("windowSettings")
        self.__settings_win.set_transient_for(mainwindow.main_window)
        assert(self.__settings_win)

        self.__ocrlangs_widget = None
        self.__scanner_device_widget = None
        self.__scanner_resolution_widget = None
    
        self.__calibration_img_frame = \
                self.__widget_tree.get_object("viewportCalibration")
        self.__calibration_img_evbox = \
                self.__widget_tree.get_object("eventboxCalibration")
        self.__calibration_img_widget = \
                self.__widget_tree.get_object("imageCalibration")
        self.__calibration_img_scaled = True
        self.__calibration_img_ratio = 1.0 # default
        self.__calibration_img = None
        self.__calibration_img_resized = None
        self.__calibration = None # will be a tuple: (CalibrationGrip, CalibrationGrip)

        self.__connect_signals()
        self.__fill_in_form()
        self.__settings_win.set_visible(True)

    @staticmethod
    def __dev_to_dev_name(dev):
        return ("%s %s (%s)" % (dev[1], dev[2], dev[3]))

    @staticmethod
    def __resolution_to_resolution_name(resolution, recommended):
        txt = ("%d" % (resolution))
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
        if self.__get_selected_resolution() != None:
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

    def __scan_calibration_page(self):
        # use a specific scanner manager for this job since
        # we want to use specific settings.
        # however, this means we have to close the other one first
        self.__scanner_mgmt.close()
        device_mgmt = PaperworkScanner()
        device_mgmt.selected_resolution = device_mgmt.CALIBRATION_RESOLUTION
        device_mgmt.selected_device = self.__get_selected_device()
        self.__calibration_img = device_mgmt.scan()
        device_mgmt.close()

        self.__calibration = (
            CalibrationGrip(0, 0),
            CalibrationGrip(self.__calibration_img.getbbox()[2],
                            self.__calibration_img.getbbox()[3]))

        self.__refresh_calibration_img()

    def __refresh_calibration_img(self, fast=False):
        assert(self.__calibration_img)

        if not fast:
            print ("Calibration window: (%d, %d)" %
                   (self.__calibration_img_frame.get_allocation().width,
                    self.__calibration_img_frame.get_allocation().height))

            if not self.__calibration_img_scaled:
                self.__calibration_img_ratio = 1.0
            else:
                wanted_width = self.__calibration_img_frame.get_allocation().width
                if int(self.__calibration_img.getbbox()[2]) > int(wanted_width):
                    width_ratio = (float(wanted_width) /
                                   self.__calibration_img.getbbox()[2])
                else:
                    width_ratio = 1.0
                wanted_height = self.__calibration_img_frame.get_allocation().height
                if int(self.__calibration_img.getbbox()[3]) > int(wanted_height):
                    height_ratio = (float(wanted_height) /
                                    self.__calibration_img.getbbox()[3])
                else:
                    height_ratio = 1.0
                if width_ratio < height_ratio:
                    self.__calibration_img_ratio = width_ratio
                else:
                    self.__calibration_img_ratio = height_ratio

            wanted_width = int(self.__calibration_img_ratio
                               * self.__calibration_img.getbbox()[2])
            wanted_height = int(self.__calibration_img_ratio
                                * self.__calibration_img.getbbox()[3])

            print "Calibration: Resize: (%d,%d) -> (%d, %d) (ratio: %f)" % (
                self.__calibration_img.getbbox()[2],
                self.__calibration_img.getbbox()[3],
                wanted_width, wanted_height, self.__calibration_img_ratio)

            self.__calibration_img_resized = self.__calibration_img.resize(
                (wanted_width, wanted_height), Image.BILINEAR)

        img = self.__calibration_img_resized.copy()
        self.__draw_calibration(ImageDraw.Draw(img))
        pixbuf = image2pixbuf(img)
        self.__calibration_img_widget.set_from_pixbuf(pixbuf)

    def __draw_calibration(self, imgdraw):
        ratio = self.__calibration_img_ratio
        for grip in self.__calibration:
            grip.draw(imgdraw, ratio)
        a_x = int(ratio * self.__calibration[0].position[0])
        a_y = int(ratio * self.__calibration[0].position[1])
        b_x = int(ratio * self.__calibration[1].position[0])
        b_y = int(ratio * self.__calibration[1].position[1])
        # make sure we are still on the image
        if a_x > self.__calibration_img_resized.getbbox()[2] - 1:
            a_x = self.__calibration_img_resized.getbbox()[2] - 1
        if a_y > self.__calibration_img_resized.getbbox()[3] - 1:
            a_y = self.__calibration_img_resized.getbbox()[3] - 1
        if b_x > self.__calibration_img_resized.getbbox()[2] - 1:
            b_x = self.__calibration_img_resized.getbbox()[2] - 1
        if b_y > self.__calibration_img_resized.getbbox()[3] - 1:
            b_y = self.__calibration_img_resized.getbbox()[3] - 1
        imgdraw.rectangle(((a_x, a_y), (b_x, b_y)),
                          outline=CalibrationGrip.COLOR)

    def __change_calibration_scale(self):
        self.__calibration_img_scaled = not self.__calibration_img_scaled
        self.__refresh_calibration_img()

    def __calibration_button_pressed_cb(self, event):
        (x, y) = event.get_coords()
        print "Pressed: (%d, %d)" % (x, y)
        selected_grip = None
        for grip in self.__calibration:
            if grip.is_on_grip((x, y), self.__calibration_img_ratio):
                selected_grip = grip
                break
        if selected_grip:
            print "Grip selected"
            selected_grip.selected = True
        else:
            print "No grip selected. Will change scale"

    def __calibration_button_released_cb(self, event):
        (x, y) = event.get_coords()
        print "Released: (%d, %d)" % (x, y)

        selected_grip = None
        for grip in self.__calibration:
            if grip.selected:
                selected_grip = grip
                break
        if selected_grip:
            selected_grip.selected = False
            new_x = x / self.__calibration_img_ratio
            new_y = y / self.__calibration_img_ratio
            if new_x < 0:
                new_x = 0
            if new_x > self.__calibration_img.getbbox()[2]:
                new_x = self.__calibration_img.getbbox()[2]
            if new_y < 0:
                new_y = 0
            if new_y > self.__calibration_img.getbbox()[3]:
                new_y = self.__calibration_img.getbbox()[3]
            selected_grip.position = (new_x, new_y)
            self.__refresh_calibration_img(fast=True)
        else:
            self.__change_calibration_scale()
    
    def __update_resolutions(self):
        device = self.__get_selected_device()
        if device == None:
            self.__possible_resolutions = []
        else:
            self.__possible_resolutions =   \
                self.__scanner_mgmt.get_possible_resolutions(device)

        scanner_table = self.__widget_tree.get_object("tableScannerSettings")
        assert(scanner_table)

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

    def __connect_signals(self):
        """
        Connect the GTK signals of the settings window.
        """
        self.__settings_win.connect("destroy", lambda x: self.__destroy())
        self.__widget_tree.get_object("buttonSettingsCancel").connect(
                "clicked", lambda x: self.__destroy())
        self.__widget_tree.get_object("buttonSettingsOk").connect(
                "clicked", lambda x: self.__apply())
        self.__widget_tree.get_object("buttonScanCalibration").connect(
                "clicked", lambda x: self.__scan_calibration_page())
        self.__calibration_img_evbox.connect("button-press-event",
                lambda x, ev: self.__calibration_button_pressed_cb(ev))
        self.__calibration_img_evbox.connect("button-release-event",
                lambda x, ev: self.__calibration_button_released_cb(ev))

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
        self.__scanner_device_widget.connect("changed", lambda x:
                                             self.__update_resolutions())
        scanner_table.attach(self.__scanner_device_widget,
                             1, # left_attach
                             2, # right_attach
                             0, # top_attach
                             1, # bottom_attach
                             xoptions=gtk.EXPAND|gtk.FILL)

        # scanner resolution
        self.__update_resolutions()

    def __destroy(self):
        """
        Hide and destroy the settings window.
        """
        self.__widget_tree.get_object("windowSettings").destroy()
