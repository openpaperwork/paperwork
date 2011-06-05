#!/usr/bin/env python

import ConfigParser
import os
import sys

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

POSSIBLE_OCR_LANGS = [ "deu", "eng", "fra", "ita", "nld", "port", "spa", "vie" ]

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

class DtGrepConfig(object):
    def __init__(self):
        self.read()

    def read(self):
        self.configparser = ConfigParser.SafeConfigParser()
        self.configparser.read([ os.path.expanduser("~/.dtgrep") ])
        if not self.configparser.has_section("Global"):
            self.configparser.add_section("Global")
        if not self.configparser.has_section("OCR"):
            self.configparser.add_section("OCR")

    @property
    def workDir(self):
        try:
            return self.configparser.get("Global", "WorkDirectory")
        except:
            return os.path.expanduser("~/papers")

    @workDir.setter
    def workDir(self, workDir):
        self.configparser.set("Global", "WorkDirectory", workDir)

    @property
    def ocrLang(self):
        try:
            return self.configparser.get("OCR", "Lang")
        except:
            return "eng"

    @ocrLang.setter
    def ocrLang(self, lang):
        self.configparser.set("OCR", "Lang", lang)

    def write(self):
        f = os.path.expanduser("~/.dtgrep")
        print "Writing %s ... " % f
        with open(f, 'wb') as fd:
            self.configparser.write(fd)
        print "Done"

class DtGrepWindow(object):
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
        self.aboutDialog.connect("close", lambda x: self.destroy())

class SettingsWindow(DtGrepWindow):
    def __init__(self, dtgrepConfig):
        DtGrepWindow.__init__(self)
        self.dtgrepConfig = dtgrepConfig
        self.settingsWindow = self.wTree.get_object("windowSettings")
        assert(self.settingsWindow)
        self.connect_signals()
        self.fill_in_form()
        self.settingsWindow.set_visible(True)

    def apply(self):
        assert(self.ocrLangs)
        self.dtgrepConfig.workDir = self.wTree.get_object("entrySettingsWorkDir").get_text()
        self.dtgrepConfig.ocrLang = POSSIBLE_OCR_LANGS[self.ocrLangs.get_active()]
        self.dtgrepConfig.write()
        return True

    def connect_signals(self):
        DtGrepWindow.connect_signals(self, self.settingsWindow)
        self.wTree.get_object("buttonSettingsCancel").connect("clicked", lambda x: self.destroy())
        self.wTree.get_object("buttonSettingsOk").connect("clicked", lambda x: self.apply() and self.destroy())
        self.wTree.get_object("buttonSettingsWorkDirSelect").connect("clicked", lambda x: self.open_file_chooser())

    def fill_in_form(self):
        # work dir
        self.wTree.get_object("entrySettingsWorkDir").set_text(self.dtgrepConfig.workDir)

        # ocr lang
        wTable = self.wTree.get_object("tableSettings")
        assert(wTable)
        self.ocrLangs = gtk.combo_box_new_text()
        idx = 0
        activeIdx = 0
        for opt in POSSIBLE_OCR_LANGS:
            self.ocrLangs.append_text(opt)
            if opt == self.dtgrepConfig.ocrLang:
                activeIdx = idx
            idx = idx + 1
        self.ocrLangs.set_active(activeIdx)
        self.ocrLangs.set_visible(True)
        wTable.attach(self.ocrLangs, 1, 2, 1, 2)

    def open_file_chooser(self):
        chooser = gtk.FileChooserDialog(action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                        buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK))
        chooser.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
        chooser.set_current_folder(self.wTree.get_object("entrySettingsWorkDir").get_text())
        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            print "Selected: %s" % (chooser.get_filename())
            self.wTree.get_object("entrySettingsWorkDir").set_text(chooser.get_filename())
        chooser.destroy()

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
    def __init__(self, config):
        self.config = config
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

        self.wTree.get_object("menuitemSettings").connect("activate", lambda x: SettingsWindow(self.config))

        self.wTree.get_object("toolbuttonSearch").connect("clicked", lambda x: SearchWindow())
        self.wTree.get_object("menuitemSearch").connect("activate", lambda x: SearchWindow())

    def destroy(self):
        destroy_wTree(self.wTree)
        gtk.main_quit()


def main():
    config = DtGrepConfig()
    MainWindow(config)
    gtk.main()

