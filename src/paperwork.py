#!/usr/bin/env python

"""
Bootstrapping code
"""

import pygtk
import gtk

from config import PaperworkConfig
from mainwindow import MainWindow

pygtk.require("2.0")

def main():
    """
    Where everything start.
    """
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

