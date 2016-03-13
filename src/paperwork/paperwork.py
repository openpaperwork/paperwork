#!/usr/bin/env python
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
Bootstrapping code
"""

import os
import sys

import gettext
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Poppler', '0.18')
gi.require_version('PangoCairo', '1.0')
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GLib
import locale
import logging
import signal

from frontend.mainwindow import ActionRefreshIndex, MainWindow
from frontend.util.config import load_config


logger = logging.getLogger(__name__)

LOCALE_LANG = ['fr', 'de']

LOCALE_PATHS = [
    os.path.join(sys.prefix, 'share', 'locale'),
    os.path.join(sys.prefix, 'local', 'share', 'locale'),
    os.path.join(os.environ.get('VIRTUAL_ENV', sys.prefix), 'locale'),
    os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'locale'),
    os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'share',
                 'locale'),
    'data/locale',
    'locale',
]


def init_logging():
    formatter = logging.Formatter(
        '%(levelname)-6s %(name)-30s %(message)s')
    handler = logging.StreamHandler()
    logger = logging.getLogger()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel({
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }[os.getenv("PAPERWORK_VERBOSE", "INFO")])


def set_locale():
    """
    Enable locale support
    """
    locale.setlocale(locale.LC_ALL, '')

    got_locales = False
    locales_path = None
    for language in LOCALE_LANG:
        for locales_path in LOCALE_PATHS:
            locale_file = os.path.join(locales_path, language, 'LC_MESSAGES',
                                       'paperwork.mo')
            logger.info("Looking for locales in '%s' ..." % (locales_path))
            if os.access(locale_file, os.R_OK):
                logger.info("Will use locales from '%s'" % (locales_path))
                got_locales = True
                break
        if got_locales:
            break
    if not got_locales:
        logger.warning("WARNING: Locales not found")
    else:
        for module in (gettext, locale):
            module.bindtextdomain('paperwork', locales_path)
            module.textdomain('paperwork')


def main():
    """
    Where everything start.
    """
    init_logging()
    set_locale()

    GObject.threads_init()

    if hasattr(GLib, "unix_signal_add"):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT,
                             Gtk.main_quit, None)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM,
                             Gtk.main_quit, None)

    try:
        config = load_config()
        config.read()

        main_win = MainWindow(config)
        ActionRefreshIndex(main_win, config).do()
        Gtk.main()

        for scheduler in main_win.schedulers.values():
            scheduler.stop()

        config.write()
    finally:
        logger.info("Good bye")


if __name__ == "__main__":
    main()
