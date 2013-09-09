#    Paperwork - Using OCR to grep dead trees the easy way
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
Paperwork configuration management code
"""

import ConfigParser
import locale
import os
import pycountry

import logging
import pyinsane.abstract_th as pyinsane
import pyocr.pyocr

logger = logging.getLogger(__name__)


class _ScanTimes(object):
    """
    Helper to find, load and rewrite the scan times stored in the configuration
    """
    __ITEM_2_CONFIG = {
        'calibration': ('Scanner', 'ScanTimeCalibration'),
        'normal': ('Scanner', 'ScanTime'),
        'ocr': ('OCR', 'OCRTime'),
    }

    def __init__(self, config):
        self.__config = config

    def __getitem__(self, item):
        cfg = self.__ITEM_2_CONFIG[item]
        try:
            return float(self.__config._configparser.get(
                cfg[0], cfg[1]))
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            return 30.0

    def __setitem__(self, item, value):
        cfg = self.__ITEM_2_CONFIG[item]
        self.__config._configparser.set(cfg[0], cfg[1], str(value))


class PaperworkConfig(object):
    """
    Paperwork config. See each accessor to know for what purpose each value is
    used.
    """
    RECOMMENDED_RESOLUTION = 300
    DEFAULT_CALIBRATION_RESOLUTION = 200
    DEFAULT_OCR_LANG = "eng"  # if really we can't guess anything

    def __init__(self):
        # values are stored directly in self._configparser
        self._configparser = ConfigParser.SafeConfigParser()
        self.scan_time = _ScanTimes(self)

        # Possible config files are evaluated in the order they are in the
        # array. The last one of the list is the default one.
        configfiles = [
            "./paperwork.conf",
            os.path.expanduser("~/.paperwork.conf"),
            ("%s/paperwork.conf"
             % (os.getenv("XDG_CONFIG_HOME",
                          os.path.expanduser("~/.config"))))
        ]

        configfile_found = False
        for self.__configfile in configfiles:
            if os.access(self.__configfile, os.R_OK):
                configfile_found = True
                logger.info("Config file found: %s" % self.__configfile)
                break
        if not configfile_found:
            logger.info("Config file not found. Will use '%s'"
                    % self.__configfile)

    def read(self):
        """
        (Re)read the configuration.

        Beware that the current work directory may affect this operation:
        If there is a 'paperwork.conf' in the current directory, it will be
        read instead of '~/.paperwork.conf', see __init__())
        """
        # smash the previous config
        self._configparser = ConfigParser.SafeConfigParser()
        self._configparser.read([self.__configfile])

        # make sure that all the sections exist
        if not self._configparser.has_section("Global"):
            self._configparser.add_section("Global")
        if not self._configparser.has_section("OCR"):
            self._configparser.add_section("OCR")
        if not self._configparser.has_section("Scanner"):
            self._configparser.add_section("Scanner")
        if not self._configparser.has_section("GUI"):
            self._configparser.add_section("GUI")
        if not self._configparser.has_section("SpellChecking"):
            self._configparser.add_section("SpellChecking")

    def __get_workdir(self):
        """
        Directory in which Paperwork must look for documents.
        Reminder: Documents are directories containing files called
        'paper.<X>.jpg', 'paper.<X>.txt' and possibly 'paper.<X>.words' ('<X>'
        being the page number).

        Returns:
            String.
        """
        try:
            return self._configparser.get("Global", "WorkDirectory")
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            return os.path.expanduser("~/papers")

    def __set_workdir(self, work_dir_str):
        """
        Set the work directory.
        """
        self._configparser.set("Global", "WorkDirectory", work_dir_str)

    workdir = property(__get_workdir, __set_workdir)

    def __get_ocr_lang(self):
        """
        OCR lang. This the lang specified to the OCR. The string here in the
        configuration is identical to the one passed to the OCR tool on the
        command line.

        String.
        """
        try:
            ocr_lang = self._configparser.get("OCR", "Lang")
            if ocr_lang == "None":
                return None
            return ocr_lang
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            pass

        # Try to guess based on the system locale what would be
        # the best OCR language

        ocr_tools = pyocr.pyocr.get_available_tools()
        if (len(ocr_tools) < 0):
            return self.DEFAULT_OCR_LANG
        ocr_langs = ocr_tools[0].get_available_languages()

        default_locale_long = locale.getdefaultlocale()[0]
        # Usually something like "fr_FR" --> we just need the first part
        default_locale = default_locale_long.split("_")[0]
        try:
            lang = pycountry.pycountry.languages.get(alpha2=default_locale)
            for ocr_lang in (lang.terminology, lang.bibliographic):
                if ocr_lang in ocr_langs:
                    return ocr_lang
        except Exception, exc:
            logger.error("Warning: Failed to figure out system language"
                   " (locale is [%s]). Will default to %s"
                   % (default_locale_long, default_locale_long))
            logger.error('Exception was: %s' % exc)
        return self.DEFAULT_OCR_LANG

    def __set_ocr_lang(self, lang):
        """
        Set the OCR lang
        """
        if lang is None:
            lang = "None"
        self._configparser.set("OCR", "Lang", lang)

    ocr_lang = property(__get_ocr_lang, __set_ocr_lang)

    def __get_spelling_lang(self):
        """
        Spell checking language.
        This is the language used for spell checking documents.

        String.
        """
        try:
            lang = self._configparser.get("SpellChecking", "Lang")
            if lang == "None":
                return None
            return lang
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            pass

        ocr_lang = self.ocr_lang
        if ocr_lang is None:
            return None

        # Try to guess the lang based on the ocr lang
        try:
            language = pycountry.languages.get(terminology=ocr_lang[:3])
        except KeyError:
            language = pycountry.languages.get(bibliographic=ocr_lang[:3])
        spelling_lang = language.alpha2
        return spelling_lang

    def __set_spelling_lang(self, lang):
        """
        Set the spell checking language
        """
        if lang is None:
            lang = "None"
        self._configparser.set("SpellChecking", "Lang", lang)

    spelling_lang = property(__get_spelling_lang, __set_spelling_lang)

    def __get_langs(self):
        """
        Convenience property. Gives all the languages used as one dictionary
        """
        ocr_lang = self.ocr_lang
        if ocr_lang is None:
            return None
        return {'ocr': ocr_lang, 'spelling': self.spelling_lang}

    langs = property(__get_langs)

    def __get_scanner_devid(self):
        """
        This is the id of the device selected by the user.

        String.
        """
        try:
            return self._configparser.get("Scanner", "Device")
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            return None

    def __set_scanner_devid(self, devid):
        """
        Set the device id selected by the user to use for scanning
        """
        self._configparser.set("Scanner", "Device", devid)

    scanner_devid = property(__get_scanner_devid, __set_scanner_devid)

    def __get_scanner_resolution(self):
        """
        This is the resolution of the scannner used for normal scans.

        String.
        """
        try:
            return int(self._configparser.get("Scanner", "Resolution"))
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            return self.RECOMMENDED_RESOLUTION

    def __set_scanner_resolution(self, resolution):
        """
        Set the scanner resolution used for normal scans.
        """
        self._configparser.set("Scanner", "Resolution", str(resolution))

    scanner_resolution = property(__get_scanner_resolution,
                                  __set_scanner_resolution)

    def __get_scanner_calibration(self):
        """
        Scanner calibration

        Returns:
            (calibration_resolution,
             ((pt_a_x, pt_a_y),
              (pt_b_x, pt_b_y)))
        """
        try:
            pt_a_x = int(self._configparser.get(
                "Scanner", "Calibration_Pt_A_X"))
            pt_a_y = int(self._configparser.get(
                "Scanner", "Calibration_Pt_A_Y"))
            pt_b_x = int(self._configparser.get(
                "Scanner", "Calibration_Pt_B_X"))
            pt_b_y = int(self._configparser.get(
                "Scanner", "Calibration_Pt_B_Y"))
            if (pt_a_x > pt_b_x):
                (pt_a_x, pt_b_x) = (pt_b_x, pt_a_x)
            if (pt_a_y > pt_b_y):
                (pt_a_y, pt_b_y) = (pt_b_y, pt_a_y)

            resolution = self.DEFAULT_CALIBRATION_RESOLUTION
            try:
                resolution = int(self._configparser.get(
                    "Scanner", "Calibration_Resolution"))
            except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
                logger.warning("Calibration resolution is not specified in the"
                               " configuration. Will assume the calibration was"
                               " done with a resolution of %ddpi" % resolution)

            return (resolution, ((pt_a_x, pt_a_y), (pt_b_x, pt_b_y)))
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            # no calibration -> no cropping -> we have to keep the whole image
            # each time
            return None

    def __set_scanner_calibration(self, calibration):
        """
        Set the scanner resolution used for normal scans.

        Arguments:
            calibration --- (calibration_resolution,
                             ((pt_a_x, pt_a_y),
                              (pt_b_x, pt_b_y)))
        """
        self._configparser.set("Scanner", "Calibration_Resolution",
                               str(calibration[0]))
        self._configparser.set("Scanner", "Calibration_Pt_A_X",
                               str(calibration[1][0][0]))
        self._configparser.set("Scanner", "Calibration_Pt_A_Y",
                               str(calibration[1][0][1]))
        self._configparser.set("Scanner", "Calibration_Pt_B_X",
                               str(calibration[1][1][0]))
        self._configparser.set("Scanner", "Calibration_Pt_B_Y",
                               str(calibration[1][1][1]))

    scanner_calibration = property(__get_scanner_calibration,
                                   __set_scanner_calibration)

    def __get_scanner_sources(self):
        """
        Indicates if the scanner source names

        Array of string
        """
        try:
            str_list = self._configparser.get("Scanner", "Sources")
            return str_list.split(",")
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            return []

    def __set_scanner_sources(self, sources):
        """
        Indicates if the scanner source names

        Array of string
        """
        str_list = ",".join(sources)
        self._configparser.set("Scanner", "Sources", str_list)

    scanner_sources = property(__get_scanner_sources, __set_scanner_sources)

    def get_scanner_inst(self):
        """
        Instantiate a pyinsance scanner and preconfigure it according to the
        configuration
        """
        scanner = pyinsane.Scanner(self.scanner_devid)
        scanner.options['resolution'].value = self.scanner_resolution
        if "Color" in scanner.options['mode'].constraint:
            scanner.options['mode'].value = "Color"
            logger.info("Scanner mode set to 'Color'")
        elif "Gray" in scanner.options['mode'].constraint:
            scanner.options['mode'].value = "Gray"
            logger.info("Scanner mode set to 'Gray'")
        else:
            logger.warn("WARNING: "
                    "Unable to set scanner mode ! May be 'Lineart'")
        return scanner

    def __get_toolbar_visible(self):
        """
        Must the toolbar(s) be displayed ?

        Boolean.
        """
        try:
            val = int(self._configparser.get("GUI", "ToolbarVisible"))
            if val == 0:
                return False
            return True
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            return True

    def __set_toolbar_visible(self, visible):
        """
        Set the OCR lang
        """
        self._configparser.set("GUI", "ToolbarVisible", str(int(visible)))

    toolbar_visible = property(__get_toolbar_visible, __set_toolbar_visible)

    def write(self):
        """
        Rewrite the configuration file. It rewrites the same file than
        PaperworkConfig.read() read.
        """
        file_path = self.__configfile
        logger.info("Writing %s ... " % file_path)
        with open(file_path, 'wb') as file_descriptor:
            self._configparser.write(file_descriptor)
        logger.info("Done")
