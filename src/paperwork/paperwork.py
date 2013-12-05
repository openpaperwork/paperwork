#!/usr/bin/env python
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
Bootstrapping code
"""

import os

import gettext
import logging
from gi.repository import GObject
from gi.repository import Gtk
import locale

import pyocr.pyocr
import pyinsane.abstract_th  # Just to start the Sane thread

from frontend import mainwindow
from backend.config import PaperworkConfig


logger = logging.getLogger(__name__)

LOCALE_PATHS = [
    # French
    ('locale/fr/LC_MESSAGES/paperwork.mo', 'locale'),
    ('/usr/local/share/locale/fr/LC_MESSAGES/paperwork.mo',
     '/usr/local/share/locale'),
    ('/usr/share/locale/fr/LC_MESSAGES/paperwork.mo', '/usr/share/locale'),

    # German
    ('locale/de/LC_MESSAGES/paperwork.mo', 'locale'),
    ('/usr/local/share/locale/de/LC_MESSAGES/paperwork.mo',
     '/usr/local/share/locale'),
    ('/usr/share/locale/de/LC_MESSAGES/paperwork.mo', '/usr/share/locale'),
]


def set_locale():
    """
    Enable locale support
    """
    locale.setlocale(locale.LC_ALL, '')

    got_locales = False
    locales_path = None
    for (fr_locale_path, locales_path) in LOCALE_PATHS:
        logger.info("Looking for locales in '%s' ..." % (fr_locale_path))
        if os.access(fr_locale_path, os.R_OK):
            logging.info("Will use locales from '%s'" % (locales_path))
            got_locales = True
            break
    if not got_locales:
        logger.warn("WARNING: Locales not found")
    else:
        for module in (gettext, locale):
            module.bindtextdomain('paperwork', locales_path)
            module.textdomain('paperwork')


def init_logging():
    formatter = logging.Formatter(
            '%(levelname)-6s %(name)-30s %(message)s')
    handler = logging.StreamHandler()
    logger = logging.getLogger()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel({
        "DEBUG" : logging.DEBUG,
        "INFO" : logging.INFO,
        "WARNING" : logging.WARNING,
        "ERROR" : logging.ERROR,
    }[os.getenv("PAPERWORK_VERBOSE", "INFO")])


def main():
    """
    Where everything start.
    """
    init_logging()
    set_locale()

    GObject.threads_init()

    try:
        config = PaperworkConfig()
        config.read()

        main_win = mainwindow.MainWindow(config)
        mainwindow.ActionRefreshIndex(main_win, config).do()
        Gtk.main()
    finally:
        logger.info("Good bye")


if __name__ == "__main__":
    main()
