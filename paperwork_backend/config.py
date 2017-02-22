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

import configparser
import logging
import os

from . import util


logger = logging.getLogger(__name__)


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


class PaperworkConfig(object):

    """
    Paperwork config. See each accessor to know for what purpose each value is
    used.
    """
    CURRENT_INDEX_VERSION = "6"

    def __init__(self):
        self.settings = {
            'workdir': PaperworkSetting(
                "Global", "WorkDirectory",
                lambda: os.path.expanduser("~/papers")),
            'index_version': PaperworkSetting(
                "Global", "IndexVersion", lambda: "-1"),
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

        configfile_found = False
        for self.__configfile in configfiles:
            if os.access(self.__configfile, os.R_OK):
                configfile_found = True
                logger.info("Config file found: %s" % self.__configfile)
                break
        if not configfile_found:
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
