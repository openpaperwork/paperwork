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
import pyocr

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
        self.section = self.__ITEM_2_CONFIG['normal'][0]

    def __getitem__(self, item):
        cfg = self.__ITEM_2_CONFIG[item]
        try:
            return float(self.__config._configparser.get(
                cfg[0], cfg[1]))
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            return 60.0

    def __setitem__(self, item, value):
        cfg = self.__ITEM_2_CONFIG[item]
        self.__config._configparser.set(cfg[0], cfg[1], str(value))

    def __get_value(self):
        return self

    value = property(__get_value)

    @staticmethod
    def load(_):
        pass

    @staticmethod
    def update(_):
        pass


def paperwork_cfg_boolean(string):
    if string.lower() == "true":
        return True
    return False


class PaperworkSetting(object):
    def __init__(self, section, token, default_value_func=lambda: None,
                 constructor=str):
        self.section = section
        self.token = token
        self.default_value_func = default_value_func
        self.constructor = constructor
        self.value = None

    def load(self, config):
        try:
            value = config.get(self.section, self.token)
            if value != "None":
                self.value = self.constructor(value)
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            pass
        self.value = self.default_value_func()

    def update(self, config):
        config.set(self.section, self.token, str(self.value))


class PaperworkScannerCalibration(object):
    DEFAULT_CALIBRATION_RESOLUTION = 200

    def __init__(self, section, token):
        self.section = section
        self.token = token
        self.value = None

    def load(self, config):
        try:
            pt_a_x = int(config.get(
                "Scanner", "Calibration_Pt_A_X"))
            pt_a_y = int(config.get(
                "Scanner", "Calibration_Pt_A_Y"))
            pt_b_x = int(config.get(
                "Scanner", "Calibration_Pt_B_X"))
            pt_b_y = int(config.get(
                "Scanner", "Calibration_Pt_B_Y"))
            if (pt_a_x > pt_b_x):
                (pt_a_x, pt_b_x) = (pt_b_x, pt_a_x)
            if (pt_a_y > pt_b_y):
                (pt_a_y, pt_b_y) = (pt_b_y, pt_a_y)

            resolution = self.DEFAULT_CALIBRATION_RESOLUTION
            try:
                resolution = int(config.get(
                    "Scanner", "Calibration_Resolution"))
            except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
                logger.warning("Calibration resolution is not specified in the"
                               " configuration. Will assume the calibration was"
                               " done with a resolution of %ddpi" % resolution)

            self.value = (resolution, ((pt_a_x, pt_a_y), (pt_b_x, pt_b_y)))
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            # no calibration -> no cropping -> we have to keep the whole image
            # each time
            self.value = None

    def update(self, config):
        config.set("Scanner", "Calibration_Resolution",
                   str(self.value[0]))
        config.set("Scanner", "Calibration_Pt_A_X",
                   str(self.value[1][0][0]))
        config.set("Scanner", "Calibration_Pt_A_Y",
                   str(self.value[1][0][1]))
        config.set("Scanner", "Calibration_Pt_B_X",
                   str(self.value[1][1][0]))
        config.set("Scanner", "Calibration_Pt_B_Y",
                   str(self.value[1][1][1]))


class PaperworkCfgStringList(list):
    def __init__(self, string):
        elements = string.split(",")
        for element in elements:
            self.append(element)

    def __str__(self):
        return ",".join(self)


class PaperworkConfig(object):
    """
    Paperwork config. See each accessor to know for what purpose each value is
    used.
    """
    RECOMMENDED_RESOLUTION = 300
    DEFAULT_OCR_LANG = "eng"  # if really we can't guess anything

    def __init__(self):
        self.backend_settings = {
            'workdir' : PaperworkSetting("Global", "WorkDirectory",
                                         lambda: os.path.expanduser("~/papers"))
        }

        self.frontend_settings = {
            'ocr_enabled' : PaperworkSetting("OCR", "Enabled", lambda: True,
                                             paperwork_cfg_boolean),
            'ocr_lang' : PaperworkSetting("OCR", "Lang", self.__get_default_ocr_lang),
            'ocr_nb_angles' : PaperworkSetting("OCR", "Nb_Angles", lambda: 4, int),
            'result_sorting' : PaperworkSetting("GUI", "Sorting", lambda: "relevance"),
            'scanner_devid' : PaperworkSetting("Scanner", "Device"),
            'scanner_resolution' : PaperworkSetting("Scanner", "Resolution",
                                                    lambda: self.RECOMMENDED_RESOLUTION,
                                                    int),
            'scanner_source' : PaperworkSetting("Scanner", "Source"),
            'scanner_sources' : PaperworkSetting("Scanner", "Sources",
                                                 lambda: PaperworkCfgStringList(""),
                                                 PaperworkCfgStringList),
            'scan_time' : _ScanTimes(self),
        }
        self.frontend_settings['spelling_lang'] = (
            PaperworkSetting("SpellChecking", "Lang",
                             self.__get_default_spellcheck_lang)
        )

        # values are stored directly in self._configparser
        self._configparser = ConfigParser.SafeConfigParser()

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

        sections = set()
        for setting in (self.backend_settings.values()
                        + self.frontend_settings.values()):
            sections.add(setting.section)
        for section in sections:
            # make sure that all the sections exist
            if not self._configparser.has_section(section):
                self._configparser.add_section(section)

        for setting in (self.backend_settings.values()
                        + self.frontend_settings.values()):
            setting.load(self._configparser)

    def __get_default_ocr_lang(self):
        # Try to guess based on the system locale what would be
        # the best OCR language

        ocr_tools = pyocr.get_available_tools()
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

    def __get_default_spellcheck_lang(self):
        ocr_lang = self.frontend_settings["ocr_lang"].value
        if ocr_lang is None:
            return None

        # Try to guess the lang based on the ocr lang
        try:
            language = pycountry.languages.get(terminology=ocr_lang[:3])
        except KeyError:
            language = pycountry.languages.get(bibliographic=ocr_lang[:3])
        spelling_lang = language.alpha2
        return spelling_lang

    def __get_langs(self):
        """
        Convenience property. Gives all the languages used as one dictionary
        """
        ocr_lang = self.frontend_settings["ocr_lang"].value
        if ocr_lang is None:
            return None
        return {
            'ocr': ocr_lang,
            'spelling': self.frontend_settings["spelling_lang"].value
        }

    langs = property(__get_langs)

    def write(self):
        """
        Rewrite the configuration file. It rewrites the same file than
        PaperworkConfig.read() read.
        """
        for setting in (self.backend_settings.values() +
                        self.frontend_settings.values()):
            setting.update(self._configparser)

        file_path = self.__configfile
        logger.info("Writing %s ... " % file_path)
        with open(file_path, 'wb') as file_descriptor:
            self._configparser.write(file_descriptor)
        logger.info("Done")

    def __getitem__(self, item):
        if item in self.frontend_settings:
            return self.frontend_settings[item]
        return self.backend_settings[item]
