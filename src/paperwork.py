#!/usr/bin/env python

import pygtk
import gtk

from config import AppConfig
from mainwindow import MainWindow

pygtk.require("2.0")

def main():
    main_win = None
    try:
        config = AppConfig()
        main_win = MainWindow(config)
        gtk.main()
    finally:
        if main_win != None:
            main_win.cleanup()

if __name__ == "__main__":
    main()

