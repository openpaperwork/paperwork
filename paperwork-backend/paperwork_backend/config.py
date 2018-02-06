#    Paperwork - Using OCR to grep dead trees the easy way
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
Paperwork configuration management code
"""

import base64
import configparser
import logging
import os
import pyocr

from . import util
from . import fs
from .util import find_language


logger = logging.getLogger(__name__)
FS = fs.GioFileSystem()

DEFAULT_OCR_LANG = "eng"  # if really we can't guess anything


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
                value = self.constructor(value)
            else:
                value = None
            self.value = value
            return
        except (configparser.NoOptionError, configparser.NoSectionError):
            pass
        self.value = self.default_value_func()

    def update(self, config):
        config.set(self.section, self.token, str(self.value))


class PaperworkURI(object):
    def __init__(self, section, token, default_value_func=lambda: None):
        self.section = section
        self.token = token
        self.default_value_func = default_value_func
        self.value = None

    def load(self, config):
        try:
            value = config.get(self.section, self.token)
            value = value.strip()
            if value != "None":
                try:
                    value = base64.decodebytes(value.encode("utf-8")).decode(
                        'utf-8')
                except Exception as exc:
                    logger.warning(
                        "Failed to decode work dir path ({})".format(value),
                        exc_info=exc
                    )
                value = FS.safe(value)
            else:
                value = None
            self.value = value
            return
        except (configparser.NoOptionError, configparser.NoSectionError):
            pass
        self.value = self.default_value_func()

    def update(self, config):
        value = FS.safe(str(self.value))
        try:
            value = base64.encodebytes(value.encode('utf-8')).decode('utf-8')
        except Exception as exc:
            logger.warning("Failed to encode work dir path ({})".format(value),
                           exc_info=exc)
        config.set(self.section, self.token, value.strip())


def get_default_ocr_lang():
    # Try to guess based on the system locale what would be
    # the best OCR language

    ocr_tools = pyocr.get_available_tools()
    if len(ocr_tools) == 0:
        return DEFAULT_OCR_LANG
    ocr_langs = ocr_tools[0].get_available_languages()

    lang = find_language()
    if hasattr(lang, 'iso639_3_code') and lang.iso639_3_code in ocr_langs:
        return lang.iso639_3_code
    if hasattr(lang, 'terminology') and lang.terminology in ocr_langs:
        return lang.terminology
    return DEFAULT_OCR_LANG


class PaperworkConfig(object):
    """
    Paperwork config. See each accessor to know for what purpose each value is
    used.
    """
    CURRENT_INDEX_VERSION = "7"

    def __init__(self):
        self.settings = {
            'workdir': PaperworkURI(
                "Global", "WorkDirectory",
                lambda: os.path.expanduser("~/papers")),
            'index_version': PaperworkSetting(
                "Global", "IndexVersion", lambda: "-1"),
            'ocr_lang': PaperworkSetting(
                "OCR", "Lang", get_default_ocr_lang
            ),
        }

        self._configparser = None

        # Possible config files are evaluated in the order they are in the
        # array. The last one of the list is the default one.
        configfiles = [
            "./paperwork.conf",
            os.path.expanduser("~/.paperwork.conf"),
            ("%s/paperwork.conf"
             % (os.getenv("XDG_CONFIG_HOME",
                          os.path.expanduser("~/.config"))))
        ]

        for self.__configfile in configfiles:
            if os.access(self.__configfile, os.R_OK):
                logger.info("Config file found: %s" % self.__configfile)
                break
        else:
            logger.info("Config file not found. Will use '%s'"
                        % self.__configfile)
        util.mkdir_p(os.path.dirname(self.__configfile))

    def read(self):
        """
        (Re)read the configuration.

        Beware that the current work directory may affect this operation:
        If there is a 'paperwork.conf' in the current directory, it will be
        read instead of '~/.paperwork.conf', see __init__())
        """
        logger.info("Reloading %s ..." % self.__configfile)

        # smash the previous config
        self._configparser = configparser.SafeConfigParser()
        self._configparser.read([self.__configfile])

        sections = set()
        for setting in self.settings.values():
            sections.add(setting.section)
        for section in sections:
            # make sure that all the sections exist
            if not self._configparser.has_section(section):
                self._configparser.add_section(section)

        for setting in self.settings.values():
            setting.load(self._configparser)

    def write(self):
        """
        Rewrite the configuration file. It rewrites the same file than
        PaperworkConfig.read() read.
        """
        logger.info("Updating %s ..." % self.__configfile)

        for setting in self.settings.values():
            setting.update(self._configparser)

        file_path = self.__configfile
        try:
            with open(file_path, 'w') as file_descriptor:
                self._configparser.write(file_descriptor)
            logger.info("Done")
        except IOError as e:
            logger.warn(
                "Cannot write to configuration file %s : %s"
                % (self.__configfile, e.strerror)
            )
            return False

        try:
            # Windows support
            util.hide_file(os.path.expanduser(os.path.join("~", ".config")))
        except Exception as exc:
            logger.warn("Failed to hide configuration file")
            logger.exception(exc)

        return True

    def __getitem__(self, item):
        return self.settings[item]
