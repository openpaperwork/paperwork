#!/usr/bin/env python3
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

gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Poppler', '0.18')
gi.require_version('PangoCairo', '1.0')

from gi.repository import GLib
from gi.repository import Gtk
import locale
import logging
import signal

import pyinsane2

from .frontend.diag import LogTracker
from .frontend.mainwindow import ActionRefreshIndex, MainWindow
from .frontend.util.config import load_config

logger = logging.getLogger(__name__)


LOCALE_PATHS = []
if getattr(sys, 'frozen', False):
    LOCALE_PATHS += [os.path.join(sys._MEIPASS, "share")]
LOCALE_PATHS += [
    ('.'),
    ('/usr/local/share/'),
    ('/usr/share/'),
]


def set_locale_windows(locales_dir):
    if not getattr(sys, 'frozen', False):
        logger.warning("Gtk locales only supported with Pyinstaller")
        return
    import ctypes
    libintl_path = os.path.abspath(os.path.join(sys._MEIPASS, "libintl-8.dll"))
    libintl = ctypes.cdll.LoadLibrary(libintl_path)
    libintl.bindtextdomain('paperwork', locales_dir)
    libintl.bind_textdomain_codeset('paperwork', 'UTF-8')
    logger.info("[Win] Locale path successfully set {}".format(locales_dir))


def set_locale():
    """
    Enable locale support
    """
    if os.name == "nt":
        lang = locale.getdefaultlocale()[0]
        os.environ['LANG'] = lang
        logger.info("System locale: {}".format(lang))
        logger.info("Glib locale: {}".format(GLib.get_language_names()))

    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        # happens e.g. when LC_ALL is set to a nonexisting locale
        logger.warning("Failed to set LC_ALL, disabling localization")
        return

    got_locales = False
    locales_path = None

    for locale_base in LOCALE_PATHS:
        locales_path = os.path.join(locale_base, "locale")
        logger.debug("Looking for locales in '%s' ..." % locales_path)
        mo_file = gettext.find("paperwork", locales_path)
        if mo_file is None:
            # No paperwork.mo found, try next path
            continue
        if not os.access(mo_file, os.R_OK):
            logger.debug("No read permission for locale '%s'" % locales_path)
            continue
        got_locales = True
        break

    if not got_locales:
        logger.warning("No suitable localization file found.")
        return

    if os.name == "nt":
        try:
            set_locale_windows(locales_path)
        except Exception as exc:
            logger.warning("Failed to set windows locale: {}".format(exc))
            logger.exception(exc)
            raise

    logger.info("Using locales in '%s'" % locales_path)
    for module in (gettext, locale):
        if hasattr(module, 'bindtextdomain'):
            module.bindtextdomain('paperwork', locales_path)
        if hasattr(module, 'textdomain'):
            module.textdomain('paperwork')


def main(hook_func=None, skip_workdir_scan=False):
    """
    Where everything start.
    """
    LogTracker.init()

    set_locale()

    if hasattr(GLib, 'set_application_name'):
        GLib.set_application_name("Paperwork")
    if hasattr(GLib, "unix_signal_add"):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT,
                             Gtk.main_quit, None)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM,
                             Gtk.main_quit, None)

    try:
        pyinsane2.init()

        config = load_config()
        config.read()

        main_win = MainWindow(config)
        ActionRefreshIndex(main_win, config,
                           skip_examination=skip_workdir_scan).do()

        if hook_func:
            hook_func(config, main_win)

        Gtk.main()

        for scheduler in main_win.schedulers.values():
            scheduler.stop()

        config.write()
    finally:
        logger.info("Good bye")


if __name__ == "__main__":
    main()
