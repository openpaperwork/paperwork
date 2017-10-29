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

import glob
import os
import sys

import gettext
import gi

gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')
gi.require_version('Poppler', '0.18')
gi.require_version('PangoCairo', '1.0')

from gi.repository import GLib
from gi.repository import Notify
import locale
import logging
import signal
import argparse

import pyinsane2

from paperwork_backend.util import mkdir_p
from paperwork_backend.util import rm_rf

from .frontend.diag import LogTracker
from .frontend.mainwindow import ActionRealQuit, __version__
from .frontend.mainwindow import MainWindow
from .frontend.util import get_locale_dirs
from .frontend.util.config import load_config

logger = logging.getLogger(__name__)

PREFIX = os.environ.get('VIRTUAL_ENV', '/usr')

LOCALE_PATHS = get_locale_dirs()


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
        break
    else:
        logger.warning("No suitable localization file found.")
        return

    if os.name == "nt":
        try:
            set_locale_windows(locales_path)
        except Exception as exc:
            logger.exception("Failed to set windows locale: {}".format(exc))
            raise

    logger.info("Using locales in '%s'" % locales_path)
    for module in (gettext, locale):
        if hasattr(module, 'bindtextdomain'):
            module.bindtextdomain('paperwork', locales_path)
        if hasattr(module, 'textdomain'):
            module.textdomain('paperwork')


def make_tessdata():
    """
    If we are in Flatpak, we must build a tessdata/ directory using the
    .traineddata files from each locale directory
    """
    tessdata_files = glob.glob("/app/share/locale/*/*.traineddata")
    if len(tessdata_files) <= 0:
        return

    localdir = os.path.expanduser("~/.local")
    base_data_dir = os.getenv(
        "XDG_DATA_HOME",
        os.path.join(localdir, "share")
    )
    tessdatadir = os.path.join(base_data_dir, "paperwork", "tessdata")

    logger.info("Assuming we are running in Flatpak."
                " Building tessdata directory {} ...".format(tessdatadir))
    rm_rf(tessdatadir)
    mkdir_p(tessdatadir)

    os.symlink("/app/share/tessdata/eng.traineddata",
               os.path.join(tessdatadir, "eng.traineddata"))
    os.symlink("/app/share/tessdata/osd.traineddata",
               os.path.join(tessdatadir, "osd.traineddata"))
    for tessdata in tessdata_files:
        logger.info("{} found".format(tessdata))
        os.symlink(tessdata, os.path.join(tessdatadir,
                                          os.path.basename(tessdata)))
    os.environ['TESSDATA_PREFIX'] = os.path.dirname(tessdatadir)
    logger.info("Tessdata directory ready")


class Main(object):
    def __init__(self):
        self.main_win = None
        self.config = None
        self.main_loop = GLib.MainLoop()

    def quit_nicely(self, *args, **kwargs):
        a = ActionRealQuit(self.main_win, self.config, self.main_loop)
        a.do()

    def main(self, hook_func=None, skip_workdir_scan=False):
        """
        Where everything start.
        """
        parser = argparse.ArgumentParser(
            description='Manages scanned documents and PDFs'
        )
        parser.add_argument('--version', action='version',
                            version=str(__version__))
        parser.add_argument(
            "--debug", "-d", default=os.getenv("PAPERWORK_VERBOSE", "INFO"),
            choices=LogTracker.LOG_LEVELS.keys(),
            help="Set verbosity level. Can also be set via env"
            " PAPERWORK_VERBOSE (e.g. export PAPERWORK_VERBOSE=INFO)"
        )
        args, unknown_args = parser.parse_known_args(sys.argv[1:])

        LogTracker.init()
        logging.getLogger().setLevel(LogTracker.LOG_LEVELS.get(args.debug))

        set_locale()

        if hasattr(GLib, "unix_signal_add"):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT,
                                 self.quit_nicely, None)
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM,
                                 self.quit_nicely, None)

        make_tessdata()
        logger.info("Initializing pyinsane ...")
        pyinsane2.init()
        try:
            logger.info("Initializing libnotify ...")
            Notify.init("Paperwork")

            self.config = load_config()
            self.config.read()

            self.main_win = MainWindow(
                self.config, self.main_loop, not skip_workdir_scan
            )
            if hook_func:
                hook_func(self.config, self.main_win)

            self.main_loop.run()

            logger.info("Writing configuration ...")
            self.config.write()

            logger.info("Stopping libnotify ...")
            Notify.uninit()
        finally:
            logger.info("Stopping Pyinsane ...")
            pyinsane2.exit()
        logger.info("Good bye")


def main(hook_func=None, skip_workdir_scan=False):
    m = Main()
    m.main(hook_func, skip_workdir_scan)


if __name__ == "__main__":
    main()
