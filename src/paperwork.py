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
    
    devices = sane.get_devices()
    if len(devices) == 0:
        print "No scanner found"
        device = None
    else:
        print "Will use device '%s'" % (str(devices[0]))
        device = sane.open(devices[0][0])

    try:
        if device != None:
            try:
                device.resolution = 250
            except AttributeError, e:
                print "WARNING: Can't set scanner resolution: " + e
            try:
                device.mode = 'Color'
            except AttributeError, e:
                print "WARNING: Can't set scanner mode: " + e

        config = AppConfig()
        MainWindow(config, device)
        gtk.main()
    finally:
        if device != None:
            device.close()

if __name__ == "__main__":
    main()

