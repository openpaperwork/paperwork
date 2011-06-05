#!/usr/bin/env python

import sys

import os
import pygtk
import glib
import gtk

pygtk.require("2.0")

POSSIBLE_UI_FILES = \
[
    "dtgrep.glade",
    "src/dtgrep.glade",
    "/usr/local/share/dtgrep/dtgrep.glade",
    "/usr/share/dtgrep/dtgrep.glade",
]

def load_uifile():
    wTree = gtk.Builder()
    has_uifile = False
    for uifile in POSSIBLE_UI_FILES:
        try:
            wTree.add_from_file(uifile)
        except glib.GError, e:
            print "Try to used UI file %s but failed: %s" % (uifile, str(e))
            continue
        has_uifile = True
        print "UI file used: "+uifile
        break
    if not has_uifile:
        raise Exception("Can't find ressource file. Aborting")
    return wTree

def connect_signals(wTree):
    wTree.get_object("mainWindow").connect("destroy", gtk.main_quit)
    wTree.get_object("toolbuttonQuit").connect("clicked", gtk.main_quit)
    wTree.get_object("menuitemQuit").connect("activate", gtk.main_quit)

def main():
    wTree = load_uifile()
    connect_signals(wTree)

    wTree.get_object("mainWindow").set_visible(True)

    gtk.main()

