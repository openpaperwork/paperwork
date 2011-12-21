#!/usr/bin/env python

"""
Bootstrapping code
"""

import gettext
import gobject
import gtk
import gtk.glade
import locale
import pygtk

from config import PaperworkConfig
from mainwindow import MainWindow

pygtk.require("2.0")


def main():
    """
    Where everything start.
    """
    locale.setlocale(locale.LC_ALL, '')
    for module in (gettext, gtk.glade):
        module.bindtextdomain('paperwork', 'locale')
        module.textdomain('paperwork')

    gobject.threads_init()

    main_win = None
    try:
        config = PaperworkConfig()
        config.read()
        main_win = MainWindow(config)
        gtk.main()
    finally:
        if main_win != None:
            main_win.cleanup()

if __name__ == "__main__":
    main()
