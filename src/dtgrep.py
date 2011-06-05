#!/usr/bin/env python

import ConfigParser
import os
import sys

import pygtk
import glib
import gtk

from docsearch import DocSearch

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
    def workdir(self):
        try:
            return self.configparser.get("Global", "WorkDirectory")
        except:
            return os.path.expanduser("~/papers")

    @workdir.setter
    def workdir(self, wd):
        self.configparser.set("Global", "WorkDirectory", wd)

    @property
    def ocrlang(self):
        try:
            return self.configparser.get("OCR", "Lang")
        except:
            return "eng"

    @ocrlang.setter
    def ocrlang(self, lang):
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
        self.aboutdialog = self.wTree.get_object("aboutdialog")
        assert(self.aboutdialog)
        self.connect_signals()
        self.aboutdialog.set_visible(True)

    def connect_signals(self):
        DtGrepWindow.connect_signals(self, self.aboutdialog)
        self.aboutdialog.connect("response", lambda x, y: self.destroy())
        self.aboutdialog.connect("close", lambda x: self.destroy())

class SettingsWindow(DtGrepWindow):
    def __init__(self, dtgrepConfig):
        DtGrepWindow.__init__(self)
        self.dtgrepConfig = dtgrepConfig
        self.settingswin = self.wTree.get_object("windowSettings")
        assert(self.settingswin)
        self.connect_signals()
        self.fill_in_form()
        self.settingswin.set_visible(True)

    def apply(self):
        assert(self.ocrlangs)
        self.dtgrepConfig.workdir = self.wTree.get_object("entrySettingsWorkDir").get_text()
        self.dtgrepConfig.ocrlang = POSSIBLE_OCR_LANGS[self.ocrlangs.get_active()]
        self.dtgrepConfig.write()
        return True

    def connect_signals(self):
        DtGrepWindow.connect_signals(self, self.settingswin)
        self.wTree.get_object("buttonSettingsCancel").connect("clicked", lambda x: self.destroy())
        self.wTree.get_object("buttonSettingsOk").connect("clicked", lambda x: self.apply() and self.destroy())
        self.wTree.get_object("buttonSettingsWorkDirSelect").connect("clicked", lambda x: self.open_file_chooser())

    def fill_in_form(self):
        # work dir
        self.wTree.get_object("entrySettingsWorkDir").set_text(self.dtgrepConfig.workdir)

        # ocr lang
        wTable = self.wTree.get_object("tableSettings")
        assert(wTable)
        self.ocrlangs = gtk.combo_box_new_text()
        idx = 0
        activeIdx = 0
        for opt in POSSIBLE_OCR_LANGS:
            self.ocrlangs.append_text(opt)
            if opt == self.dtgrepConfig.ocrlang:
                activeIdx = idx
            idx = idx + 1
        self.ocrlangs.set_active(activeIdx)
        self.ocrlangs.set_visible(True)
        wTable.attach(self.ocrlangs, 1, 2, 1, 2)

    def open_file_chooser(self):
        chooser = gtk.FileChooserdialog(action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                        buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK))
        chooser.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
        chooser.set_current_folder(self.wTree.get_object("entrySettingsWorkDir").get_text())
        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            print "Selected: %s" % (chooser.get_filename())
            self.wTree.get_object("entrySettingsWorkDir").set_text(chooser.get_filename())
        chooser.destroy()

class SearchWindow(DtGrepWindow):
    def __init__(self, docsearch):
        DtGrepWindow.__init__(self)
        self.docsearch = docsearch
        self.searchwin = self.wTree.get_object("windowSearch")
        assert(self.searchwin)
        self.connect_signals()
        self.searchwin.set_visible(True)

    def update_results(self, objsrc):
        txt = self.wTree.get_object("entrySearch").get_text()
        print "Search: " + txt

    def apply(self):
        # TODO
        return True

    def connect_signals(self):
        DtGrepWindow.connect_signals(self, self.searchwin)
        self.wTree.get_object("entrySearch").connect("changed", self.update_results)
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

    def open_search_window(self, objsrc):
        dsearch = DocSearch(self.config.workdir)
        dsearch.index() # TODO: callback -> progress bar
        SearchWindow(dsearch)

    def connect_signals(self):
        self.mainWindow.connect("destroy", lambda x: self.destroy())
        self.wTree.get_object("toolbuttonQuit").connect("clicked", lambda x: self.destroy())
        self.wTree.get_object("menuitemQuit").connect("activate", lambda x: self.destroy())

        self.wTree.get_object("menuitemAbout").connect("activate", lambda x: AboutDialog())

        self.wTree.get_object("menuitemSettings").connect("activate", lambda x: SettingsWindow(self.config))

        self.wTree.get_object("toolbuttonSearch").connect("clicked", self.open_search_window)
        self.wTree.get_object("menuitemSearch").connect("activate", self.open_search_window)

    def destroy(self):
        destroy_wTree(self.wTree)
        gtk.main_quit()


def main():
    config = DtGrepConfig()
    MainWindow(config)
    gtk.main()

