#!/usr/bin/env python

"""
Bootstrapping code
"""

import os
import sys

import gettext
import gobject
import gtk
import gtk.glade
import locale
import pygtk

from controller.mainwindow import MainWindow
from model.config import PaperworkConfig
from model.scanner import PaperworkScanner
from model.scanner import sane_init
from model.scanner import sane_exit

pygtk.require("2.0")

# we use the french locale as reference to know where to look for locales
# order matters
LOCALE_PATHS = [
    ('locale/fr/LC_MESSAGES/paperwork.mo', 'locale'),
    ('/usr/local/share/locale/fr/LC_MESSAGES/paperwork.mo',
     '/usr/local/share/locale'),
    ('/usr/share/locale/fr/LC_MESSAGES/paperwork.mo', '/usr/share/locale'),
]

def main():
    """
    Where everything start.
    """
    locale.setlocale(locale.LC_ALL, '')

    got_locales = False
    locales_path = None
    for (fr_locale_path, locales_path) in LOCALE_PATHS:
        print "Looking for locales in '%s' ..." % (fr_locale_path)
        if os.access(fr_locale_path, os.R_OK):
            print "Will use locales from '%s'" % (locales_path)
            got_locales = True
            break
    if not got_locales:
        print "WARNING: Locales not found"
    else:
        for module in (gettext, gtk.glade):
            module.bindtextdomain('paperwork', locales_path)
            module.textdomain('paperwork')

    gobject.threads_init()
    sane_init()

    try:
        config = PaperworkConfig()
        config.read()

        device = PaperworkScanner()
        device.load_settings_from_config(config)

        main_win = MainWindow(config, device)
        main_win.actions['new_doc'][1].do()
        main_win.actions['reindex'][1].do()
        gtk.main()
        print "Good bye"
    finally:
        sane_exit()


if __name__ == "__main__":
    main()
