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
import sys

import gettext
import gobject
import gtk
import gtk.glade
import locale
import pygtk

import pyinsane.abstract_th  # Just to start the Sane thread

from frontend.mainwindow import MainWindow
from backend.config import PaperworkConfig

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
