#!/usr/bin/env python

import sys

import pygtk
import gtk

pygtk.require("2.0")

if __name__ == "__main__":
    uifile = "dtgrep.glade"
    wTree = gtk.Builder()
    wTree.add_from_file(uifile)

    window = wTree.get_object("MainWindow")
    if window:
        window.connect("destroy", gtk.main_quit)
        window.set_visible(True)
    
    gtk.main()
