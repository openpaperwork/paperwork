#!/usr/bin/env python

import pygtk
import gtk

from aboutdialog import AboutDialog
from config import AppConfig
from mainwindow import MainWindow

pygtk.require("2.0")

def main():
    m = None
    try:
        config = AppConfig()
        m = MainWindow(config)
        gtk.main()
    finally:
        if m != None:
            m.cleanup()

if __name__ == "__main__":
    main()

