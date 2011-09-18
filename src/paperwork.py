#!/usr/bin/env python

import pygtk
import gtk
import sane

from aboutdialog import AboutDialog
from config import AppConfig
from mainwindow import MainWindow

pygtk.require("2.0")

def main():
    sane.init()
    config = AppConfig()
    MainWindow(config)
    gtk.main()

if __name__ == "__main__":
    main()

