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

import pyinsane.abstract_th # Just to start the Sane thread

from controller.mainwindow import MainWindow
from model.config import PaperworkConfig

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

    config = PaperworkConfig()
    config.read()

    main_win = MainWindow(config)
    main_win.actions['new_doc'][1].do()
    main_win.actions['reindex'][1].do()
    gtk.main()
    print "Good bye"


if __name__ == "__main__":
    main()
