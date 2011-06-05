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

def destroy_wTree(wTree):
    wTree.get_object("mainWindow").destroy()
    wTree.get_object("aboutdialog").destroy()
    wTree.get_object("windowSearch").destroy()
    wTree.get_object("windowSettings").destroy()

class DtGrepWindow:
    def __init__(self):
        # we have to recreate new dialogs each time, otherwise, when the user
        # destroy the dialog, we won't be able to redisplay it
        self.wTree = load_uifile()

    def connect_signals(self, win):
        win.connect("destroy", lambda x: self.destroy())

    def destroy(self):
        destroy_wTree(self.wTree)

class AboutDialog(DtGrepWindow):
    def __init__(self):
        DtGrepWindow.__init__(self)
        self.aboutDialog = self.wTree.get_object("aboutdialog")
        assert(self.aboutDialog)
        self.connect_signals()
        self.aboutDialog.set_visible(True)

    def connect_signals(self):
        DtGrepWindow.connect_signals(self, self.aboutDialog)
        self.aboutDialog.connect("response", lambda x, y: self.destroy())
        dialog.connect("close", lambda x: self.destroy())

class SettingsWindow(DtGrepWindow):
    def __init__(self):
        DtGrepWindow.__init__(self)
        self.settingsWindow = self.wTree.get_object("windowSettings")
        assert(self.settingsWindow)
        self.connect_signals()
        self.settingsWindow.set_visible(True)

    def apply(self):
        # TODO
        return True

    def connect_signals(self):
        DtGrepWindow.connect_signals(self, self.settingsWindow)
        self.wTree.get_object("buttonSettingsCancel").connect("clicked", lambda x: self.destroy())
        self.wTree.get_object("buttonSettingsOk").connect("clicked", lambda x: self.apply() and self.destroy())

class SearchWindow(DtGrepWindow):
    def __init__(self):
        DtGrepWindow.__init__(self)
        self.searchWindow = self.wTree.get_object("windowSearch")
        assert(self.searchWindow)
        self.connect_signals()
        self.searchWindow.set_visible(True)

    def apply(self):
        # TODO
        return True

    def connect_signals(self):
        DtGrepWindow.connect_signals(self, self.searchWindow)
        self.wTree.get_object("buttonSearchCancel").connect("clicked", lambda x: self.destroy())
        self.wTree.get_object("buttonSearchOk").connect("clicked", lambda x: self.apply() and self.destroy())

class MainWindow:
    def __init__(self):
        self.wTree = load_uifile()
        self.mainWindow = self.wTree.get_object("mainWindow")
        assert(self.mainWindow)
        self.connect_signals()
        self.mainWindow.set_visible(True)

    def connect_signals(self):
        self.mainWindow.connect("destroy", lambda x: self.destroy())
        self.wTree.get_object("toolbuttonQuit").connect("clicked", lambda x: self.destroy())
        self.wTree.get_object("menuitemQuit").connect("activate", lambda x: self.destroy())

        self.wTree.get_object("menuitemAbout").connect("activate", lambda x: AboutDialog())

        self.wTree.get_object("menuitemSettings").connect("activate", lambda x: SettingsWindow())

        self.wTree.get_object("toolbuttonSearch").connect("clicked", lambda x: SearchWindow())
        self.wTree.get_object("menuitemSearch").connect("activate", lambda x: SearchWindow())

    def destroy(self):
        destroy_wTree(self.wTree)
        gtk.main_quit()


def main():
    MainWindow()
    gtk.main()

